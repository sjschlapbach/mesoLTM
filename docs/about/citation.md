# Citation

**If you use `mesoltm` in academic or other work, please cite this repository.**
A machine-readable entry is provided in
[`CITATION.cff`](https://github.com/sjschlapbach/mesoLTM/blob/master/CITATION.cff).

!!! warning "DOI pending — placeholder citation"
    A DOI has **not yet been registered** for `mesoltm`. The entries below are
    placeholders. Once a DOI is minted (e.g. via [Zenodo](https://zenodo.org/), by
    enabling the GitHub–Zenodo integration and cutting a release), it will be added
    to `CITATION.cff`, this page, and the `README`.

## Repository (primary)

> J. Schlapbach, *mesoLTM: a mesoscopic (individual-vehicle) Link Transmission
> Model*. Software, version 0.1.0.
> <https://github.com/sjschlapbach/mesoLTM>

```bibtex
@software{mesoltm,
  author  = {Schlapbach, Julius},
  title   = {{mesoLTM}: a mesoscopic (individual-vehicle) Link Transmission Model},
  version = {0.1.0},
  url     = {https://github.com/sjschlapbach/mesoLTM},
  note    = {TODO: DOI pending registration (e.g. via Zenodo)},
  year    = {2026}
}
```

## Paper (secondary)

Please also cite the paper whose model `mesoltm` implements, and whose `abmmeso`
package (by Felipe de Souza, AGPL-3.0) it adapts:

> F. de Souza, O. Verbas, J. Auld, C. M. J. Tampère, *"A mesoscopic
> link-transmission-model able to track individual vehicles"*, Simulation
> Modelling Practice and Theory **140** (2025) 103088.
> DOI: [10.1016/j.simpat.2025.103088](https://doi.org/10.1016/j.simpat.2025.103088)

```bibtex
@article{deSouza2025mesoLTM,
  author  = {de Souza, Felipe and Verbas, Omer and Auld, Joshua and Tamp{\`e}re, Chris M. J.},
  title   = {A mesoscopic link-transmission-model able to track individual vehicles},
  journal = {Simulation Modelling Practice and Theory},
  volume  = {140},
  pages   = {103088},
  year    = {2025},
  doi     = {10.1016/j.simpat.2025.103088}
}
```

The deviations of `mesoltm` from the paper's formulation are documented in
[Deviations from the paper](../model/deviations-from-the-paper.md).
