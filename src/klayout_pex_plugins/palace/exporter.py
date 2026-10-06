#
# --------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2026 Martin Jan Köhler and Harald Pretl
# Johannes Kepler University, Institute for Integrated Circuits.
#
# This file is part of klayout-pex-plugin-palace
# (see https://github.com/iic-jku/klayout-pex-plugin-palace).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
# SPDX-License-Identifier: GPL-3.0-or-later
# --------------------------------------------------------------------------------
#

"""
The exporter ``palace``: an Electrostatic problem whose result is the Maxwell
capacitance matrix of every net, floating conductor and the ground plane.

Palace writes it to ``postpro/terminal-C.csv``; terminal *i* there is the group
with tag *i* in ``mesh.json``. Paths in the config are relative, so Palace runs
in the output directory: ``cd DIR && palace config.json``.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Mapping, Optional

from klayout_pex.log import info
from klayout_pex.plugin_api.v1 import PEX25DSceneExporter
from klayout_pex_plugins.gmsh import (LENGTH_UNIT_M, GmshMeshOptions, MeshResult,
                                      parse_options, write_mesh)

if TYPE_CHECKING:
    from klayout_pex_protobuf.kpex.pex25d.pex25d_scene_pb2 import PEX25DScene

OUTER_BOUNDARY_CONDITIONS = {'zero_charge': 'ZeroCharge', 'ground': 'Ground'}


@dataclass
class PalaceExporterOptions(GmshMeshOptions):
    """The mesh's settings, and Palace's."""

    order: int = 1
    """
    Polynomial order of the finite elements. 2 is about 1% more accurate with the
    default mesh, at about 9 times the run time.
    """

    outer_boundary: str = 'zero_charge'
    """
    The domain box: ``zero_charge`` (no field crosses it) or ``ground`` (0 V). Each
    biases the matrix the other way; a larger field margin shrinks both effects.
    """

    linear_tol: float = 1.0e-8
    """Relative residual of the linear solver."""

    linear_max_iterations: int = 200

    def __post_init__(self):
        super().__post_init__()
        if self.order < 1:
            raise ValueError("'order' must be at least 1")
        if self.outer_boundary not in OUTER_BOUNDARY_CONDITIONS:
            raise ValueError(f"'outer_boundary' must be one of "
                             f"{', '.join(OUTER_BOUNDARY_CONDITIONS)}")


class PalaceSceneExporter(PEX25DSceneExporter):
    """Write a Palace electrostatic deck from a resolved PEX25D scene."""

    name: ClassVar[str] = 'palace'
    default_prefix: ClassVar[str] = ''

    def export(self,
               scene: PEX25DScene,
               *,
               output_dir_path: str,
               prefix: str = '',
               options: Optional[Mapping[str, Any]] = None) -> List[str]:
        """Return the config first, then the mesh and the JSON naming its groups."""
        settings = parse_options(PalaceExporterOptions, options, self.name)
        prefix = prefix or self.default_prefix
        mesh = write_mesh(scene, settings, output_dir_path, prefix)

        config_path = os.path.join(output_dir_path, f"{prefix}config.json")
        with open(config_path, 'w', encoding='utf-8') as file:
            json.dump(palace_config(mesh, settings), file, indent=2)
            file.write('\n')
        info(f"Run Palace in {output_dir_path}: palace {os.path.basename(config_path)}")
        return [config_path, *mesh.paths]


def palace_config(mesh: MeshResult, settings: PalaceExporterOptions) -> Dict[str, Any]:
    boundaries: Dict[str, Any] = {
        'Terminal': [{'Index': group.tag, 'Attributes': [group.tag]}
                     for group in mesh.terminals],
    }
    if mesh.outer_boundary is not None:
        boundaries[OUTER_BOUNDARY_CONDITIONS[settings.outer_boundary]] = {
            'Attributes': [mesh.outer_boundary.tag]}
    return {
        'Problem': {
            'Type': 'Electrostatic',
            'Verbose': 2,
            'Output': 'postpro',
        },
        'Model': {
            'Mesh': os.path.basename(mesh.msh_path),
            'L0': LENGTH_UNIT_M,
        },
        'Domains': {
            'Materials': [{'Attributes': [group.tag], 'Permittivity': group.permittivity}
                          for group in mesh.dielectrics],
        },
        'Boundaries': boundaries,
        'Solver': {
            'Order': settings.order,
            'Linear': {
                'Type': 'BoomerAMG',
                'KSPType': 'CG',
                'Tol': settings.linear_tol,
                'MaxIts': settings.linear_max_iterations,
            },
        },
    }
