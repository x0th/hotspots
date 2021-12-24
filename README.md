# Hotspots

A Rust profiler for Sublime Text

## Dependencies

To run the profiler, you will need to install:

- [cargo](https://crates.io/)

- llvm-profdata and llvm-cov

You can get the above LLVM-specific tools as part of [llvm](https://github.com/llvm-mirror/llvm) or by running

```
rustup component add llvm-tools-preview
```

## Installation

You can install the package from [packagecontrol.io](packagecontrol.io).

## Usage

When viewing a Rust (.rs) file in a Cargo repository, press `alt+h` to run the profiler.

Note that this runs the following shell commands:

```
cargo rustc
cargo run
llvm-profdata ...
llvm-cov ...
```

To clear the profiling data, press `ctrl/cmd+alt+h`.

You can also find the above commands in the Command Palette by search for Hotspots.