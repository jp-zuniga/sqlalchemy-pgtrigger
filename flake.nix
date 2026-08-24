{
  description = "basic dev env";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = {
    self,
    nixpkgs,
    nixpkgs-unstable,
  }: let
    forAllSystems = nixpkgs.lib.genAttrs ["x86_64-linux" "aarch64-linux"];
    pkgsFor = forAllSystems (system: nixpkgs.legacyPackages.${system});
    unstableFor = forAllSystems (system: nixpkgs-unstable.legacyPackages.${system});
  in {
    formatter = forAllSystems (system: pkgsFor.${system}.alejandra);
    devShells = forAllSystems (system: let
      pkgs = pkgsFor.${system};
      unstable = unstableFor.${system};
    in {
      default = pkgs.mkShell {
        packages = [
          pkgs.prettier
          unstable.just
          unstable.uv
        ];
      };
    });
  };
}
