
{ pkgs ? import <nixpkgs> {} }:
  pkgs.mkShell {
    # build tools
    nativeBuildInputs = with pkgs; [
      # (python310.withPackages (ps: with ps; [requests matplotlib tkinter alive-progress]))
      python3
      poetry
    ];

    # libraries/dependencies
    buildInputs = with pkgs; [];

    LD_LIBRARY_PATH = "${pkgs.stdenv.cc.cc.lib}/lib";
}
