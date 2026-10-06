# klayout-pex-plugin-palace

[Palace](https://awslabs.github.io/palace/) electrostatic decks from [KLayout-PEX](https://github.com/iic-jku/klayout-pex) PEX25D scenes: the capacitance matrix of every net, floating conductor and the ground plane, by FEM.

## Usage

```bash
pip install klayout-pex-plugin-palace
pex25d export cell.pex25d --to palace --out_dir deck
cd deck && palace -np 4 config.json
```

- **Output of the exporter:**
  - `config.json`
  - `mesh.msh` and `mesh.json`, from [klayout-pex-plugin-gmsh](https://github.com/iic-jku/klayout-pex-plugin-gmsh)
- **Run Palace in the deck directory:** paths in the config are relative.
- **Results:** in `postpro/`
  - `terminal-C.csv`: the Maxwell matrix
  - `terminal-Cm.csv`: mutual capacitances
  - terminal *i* is the group with tag *i* in `mesh.json`
- **In IIC-OSIC-TOOLS:** Palace is in `/foss/tools/bin`. As root, `mpirun` refuses to start, so use `palace -serial config.json`.

## Options

The mesh options of klayout-pex-plugin-gmsh, plus:

| Option | Default | Meaning |
| --- | --- | --- |
| `order` | 1 | Polynomial order of the finite elements; 2 is about 1% more accurate with the default mesh, at about 9 times the run time |
| `outer_boundary` | `zero_charge` | Domain box: `zero_charge` (no field crosses it) or `ground` (0 V) |
| `linear_tol` | 1e-8 | Relative residual of the linear solver |
| `linear_max_iterations` | 200 | |

Pass them with `pex25d export --option NAME=VALUE` (klayout-pex 0.6.3 or later) or `options={...}` in Python.

## Development

```bash
poetry install    # uses ../klayout-pex-plugin-gmsh until it is on PyPI
poetry run pytest # runs Palace too, if it is on PATH
```
