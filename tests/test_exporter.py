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

"""The Palace deck: its config against the mesh groups, and a run where Palace is installed."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from klayout_pex import pex25d


def export(scene, tmp_path: Path, **options):
    written = pex25d.export(scene, 'palace', str(tmp_path), options=options)
    config, groups = (json.loads(Path(path).read_text()) for path in (written[0], written[2]))
    return written, config, groups


def test_registered_as_exporter_plugin():
    info = pex25d.exporter_registry().get_info('palace')
    assert info.distribution == 'klayout-pex-plugin-palace'
    assert info.target == 'klayout_pex_plugins.palace:create_exporter'


def test_config_matches_the_mesh_groups(two_nets, tmp_path: Path):
    written, config, groups = export(two_nets, tmp_path)
    assert written == [str(tmp_path / name) for name in ('config.json', 'mesh.msh', 'mesh.json')]

    assert config['Problem']['Type'] == 'Electrostatic'
    assert config['Model'] == {'Mesh': 'mesh.msh', 'L0': 1e-6}
    assert config['Domains']['Materials'] == [
        {'Attributes': [group['tag']], 'Permittivity': group['permittivity']}
        for group in groups['dielectrics']]
    assert config['Boundaries']['Terminal'] == [
        {'Index': group['tag'], 'Attributes': [group['tag']]} for group in groups['terminals']]
    assert [group['name'] for group in groups['terminals']] == ['subs', 'neta', 'netb', 'F']
    assert config['Boundaries']['ZeroCharge'] == {'Attributes': [groups['outer_boundary']['tag']]}
    assert config['Solver']['Order'] == 1


def test_options(two_nets, tmp_path: Path):
    written, config, groups = export(two_nets, tmp_path, outer_boundary='ground', order=3)
    assert 'ZeroCharge' not in config['Boundaries']
    assert config['Boundaries']['Ground'] == {'Attributes': [groups['outer_boundary']['tag']]}
    assert config['Solver']['Order'] == 3


def test_prefix_names_every_file(two_nets, tmp_path: Path):
    written = pex25d.export(two_nets, 'palace', str(tmp_path), prefix='tiny_')
    assert [Path(path).name for path in written] == ['tiny_config.json', 'tiny_mesh.msh',
                                                     'tiny_mesh.json']
    assert json.loads(Path(written[0]).read_text())['Model']['Mesh'] == 'tiny_mesh.msh'


@pytest.mark.parametrize('options, message', [
    ({'outer_boundary': 'open'}, "'outer_boundary' must be one of zero_charge, ground"),
    ({'order': 0}, "'order' must be at least 1"),
    ({'order': 2.0}, "'order' must be int"),
    ({'write_stl': True}, "unexpected keyword argument 'write_stl'"),
], ids=['boundary', 'order', 'order-type', 'unknown'])
def test_invalid_options_are_export_errors(two_nets, tmp_path: Path, options, message: str):
    with pytest.raises(pex25d.ExportError, match=message):
        pex25d.export(two_nets, 'palace', str(tmp_path), options=options)


@pytest.mark.skipif(shutil.which('palace') is None, reason="Palace is not installed")
def test_palace_solves_the_deck(two_nets, tmp_path: Path):
    export(two_nets, tmp_path)
    subprocess.run(['palace', '-serial', 'config.json'], cwd=tmp_path, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    with open(tmp_path / 'postpro' / 'terminal-Cm.csv') as file:
        rows = [[float(value) for value in row[1:]] for row in list(csv.reader(file))[1:]]
    assert len(rows) == 4 and all(len(row) == 4 for row in rows)
    for i in range(4):
        for j in range(4):
            assert rows[i][j] == pytest.approx(rows[j][i], rel=1e-6)
            if i != j:
                assert rows[i][j] > 0      # mutual capacitances: every pair couples
