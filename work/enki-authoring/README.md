# enki

`enki` is a PLAN runtime.

## Running

```sh
# compiling
nix build
# testing
nix flake check -L
# full CI check (tests followed by the default package build)
make nix-ci
```

## Entering a reaver dev environment

```sh
## start, or resume
x/boot
## reboot (clear current snapshots)
x/boot --reset
```
