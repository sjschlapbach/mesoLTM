# License & attribution

## License

`mesoltm` is distributed under the **GNU Affero General Public License v3.0 or
later (AGPL-3.0-or-later)**. See
[`LICENSE`](https://github.com/sjschlapbach/mesoLTM/blob/master/LICENSE) for the
full text.

The AGPL is used because `mesoltm` **adapts AGPL-3.0 source** — the `abmmeso`
package by Felipe de Souza — and the AGPL requires derivative works to be
distributed under the same license.

## Attribution

`mesoltm` is a re-implementation of the mesoscopic (individual-vehicle) Link
Transmission Model and reuses/adapts the core model logic of the
[`abmmeso`](https://github.com/felasouza/abmmeso) package by Felipe de Souza
(AGPL-3.0). The core link demand/supply dynamics, the integer capacity
discretisation, and the node flow-resolution algorithms (one-to-one, diverge,
merge, and general node models) follow that work, which is described in:

> F. de Souza, O. Verbas, J. Auld, C. M. J. Tampère, *"A mesoscopic
> link-transmission-model able to track individual vehicles"*, Simulation
> Modelling Practice and Theory **140** (2025) 103088.
> DOI: [10.1016/j.simpat.2025.103088](https://doi.org/10.1016/j.simpat.2025.103088)

Full attribution is recorded in
[`NOTICE`](https://github.com/sjschlapbach/mesoLTM/blob/master/NOTICE). Every
source file carries an AGPL notice, and files with logic ported from `abmmeso` or
the paper additionally cite the publication.

See [Citation](citation.md) for how to cite `mesoltm` and the paper.
