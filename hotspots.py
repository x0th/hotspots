import sublime
import sublime_plugin
import subprocess
import os

class HotspotsRunCommand(sublime_plugin.TextCommand):
	def tranform_count(self, count_str):
		"""
		Transforms count number from the form of llvm-cov to a float
		llvm-cov format is num[|k|M|G|T|P|E|Z|Y]
		"""
		try:
			if count_str[-1] >= '0' and count_str[-1] <= '9':
				count = float(count_str)
			else:
				count = float(count_str[:-1]) * 1000 * (['', 'k', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y'].index(count_str[-1]))
			return count
		except Exception as e:
			pass

	def hex_to_rgb(self, hex):
		"""
		Converts hex string in the form #FFFFFF to an RGB array [255, 255, 255]
		"""
		return [int(hex[i:i+2], 16) for i in range(1, 6, 2)]

	def get_color(self, val, lower_color, upper_color, n=100):
		"""
		Returns a color of gradient between lower_color and upper_color at point val
		val is assumed to be a percent value
		"""
		start_rgb = self.hex_to_rgb(lower_color)
		end_rgb = self.hex_to_rgb(upper_color)

		out_rgb = [
			int(start_rgb[i] + (val / (n-1)) * (end_rgb[i] - start_rgb[i]))
			for i in range(3)
		]

		# get hex out of rgb
		return "#"+"".join(["0{0:x}".format(v) if v < 16 else
            "{0:x}".format(v) for v in out_rgb])

	def run_outside_commands(self, settings):
		"""
		Runs external commands to create the profile

		The commands are
		export RUSTFLAGS=-Zinstrument-coverage; cargo rustc -- compile the program
		export RUSTFLAGS=-Zinstrument-coverga; cargo run -- run an executable to create the profile
		llvm-profdata ... -- merge profdata
		llvm-cov ... - create a coverage profile

		Additional args can be passed at the start of each command via settings (e.g. "wsl" to run the commands in wsl)
		"""
		os.chdir(self.view.file_name().split('src')[0])
		
		cargo = settings.get('cargo', '~/.cargo/bin/cargo')
		llvm_profdata = settings.get('llvm_profdata', 'llvm-profdata')
		llvm_cov = settings.get('llvm_cov', 'llvm-cov')
		additional_args = settings.get('additional_args', [])
		with open('Cargo.toml', 'r') as f:
			lines = f.readlines()
			for l in lines:
				if 'name = ' in l:
					app_name = l.split('name = ')[1][1:-2]

		subprocess.call(additional_args + ['export', 'RUSTFLAGS=-Zinstrument-coverage', ';', cargo, 'rustc'])
		subprocess.call(additional_args + ['export', 'RUSTFLAGS=-Zinstrument-coverage', ';', cargo, 'run'])
		subprocess.call(additional_args + [llvm_profdata, 'merge', '-output=merged.profdata', '-instr', 'default.profraw'])
		return subprocess.check_output(additional_args + [llvm_cov, 'show', 'target/debug/' + app_name, '-instr-profile=merged.profdata'], stderr=subprocess.STDOUT).decode('utf-8')

	def get_hotspots(self, filename, profdata):
		"""
		Parses profdata of filename to the needed format
		Returns parsed profdata, total count of executed instructions and greatest length of a count string (for padding)
		"""
		hotspots = []
		total_count = 0
		greatest_len = 0

		j = -1
		if '|' in profdata[0]:
			# if there's only one source file in the executable, it will be at the start of profdata without filename
			j = 0
		else:
			# otherwise, have to search for the filename
			for i in range(len(profdata)):
				if filename in profdata[i]:
					j = i + 1
					break

		# profile of a correct line is
		# line_num | run_count | line_code
		line = profdata[j].strip()
		while(line != ''):
			try:
				split = line.split('|')
				count_str = split[1].strip()
				if count_str != '0' and count_str != '':
					count = self.tranform_count(count_str)
					
					hotspots.append((int(split[0]) - 1, count_str, int(count)))
					
					total_count += int(count)

					if len(count_str) >= greatest_len:
						greatest_len = len(count_str)
			except Exception as e:
				pass

			j += 1
			line = profdata[j].strip()
		
		return (hotspots, total_count, greatest_len)

	def run(self, edit):
		settings = sublime.load_settings('Hotspots.sublime-settings')
		lower_color = settings.get('lower_color', '#FFFFFF')
		upper_color = settings.get('upper_color', '#FFFFFF')

		# filename is file_name of the view plus a / at the start
		filename = '/' + os.path.basename(self.view.file_name())
		profdata = self.run_outside_commands(settings).split('\n')
		hotspots, total_count, greatest_len = self.get_hotspots(filename, profdata)

		regions = {}
		counts = {}
		colors = {}
		for h in hotspots:
			percent = self.tranform_count(h[1]) / float(total_count) * 100

			if percent not in regions:
				regions[percent] = []
			if percent not in counts:
				counts[percent] = []
			
			# because each region starts and ends on the same line in column 0, nothing will be underlined in the file
			regions[percent].append(sublime.Region(self.view.text_point(h[0], 0), self.view.text_point(h[0], 0)))
			
			padding = '&nbsp;' * (greatest_len - len(h[1]))
			# by default, only show the run count of a line
			count = h[1] + padding
			# if show_percent is set, we also show run count percentage of a line
			if settings.get('show_percent', True):
				count = count + ' | ' + '{:05.2f}'.format(percent) + '%'
			counts[percent].append(count)
			
			# we only calculate gradient color if monotone_color is False
			if settings.get('monotone_color', False):
				colors[percent] = lower_color
			else:
				colors[percent] = self.get_color(percent, lower_color, upper_color)

		# draw the regions in the view
		i = 0
		for key in regions:
			self.view.add_regions('hotspots-' + str(i), regions[key], annotations=counts[key], annotation_color=colors[key])
			i += 1

class HotspotsRemoveCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		# because there's no way to search for regions by regex, we have to
		# first get_regions to see if the regions exist, then delete them
		# my guess would be that it's pretty slow. Too bad.
		i = 0
		while len(self.view.get_regions('hotspots-' + str(i))) != 0:
			self.view.erase_regions('hotspots-' + str(i))
			i += 1