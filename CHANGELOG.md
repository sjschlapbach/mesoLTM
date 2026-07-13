## [0.3.0] - 2026-07-13

### Features

- Add possibility to peek at flows across node in upcoming step (#13)

### Enhancements

- Store critical and jam occupancy as additional auxiliary link attributes
- Directly implement demand extraction with movement key (#12)

### Bug Fixes

- Update departure time to actual departure time instead of scheduled departure time
- Resolve linting errors and example script failures (#11)

### Miscellaneous Tasks

- *(release)* Update changelog for version 0.2.0
- Update changelog generation for github release text content
- *(release)* V0.3.0
## [0.2.0] - 2026-07-11

### Features

- Add possibility for vehicle to be re-injected and complete multiple trips within single simulation run (#10)

### Enhancements

- Improve plotting of complex networks with multiple links between pairs of nodes

### Refactor

- Enhance quality of typing throughout library (#9)

### Miscellaneous Tasks

- *(release)* Update changelog for version 0.1.1
- Simplify implementation for static and dynamic visualizations through shared logic
- *(release)* V0.2.0
## [0.1.1] - 2026-07-09

### Miscellaneous Tasks

- *(release)* Update changelog for version 0.1.0
- Update README with badges and links to documentation and pypi deployment
- Add progress bar to simulation execution
- *(release)* V0.1.1
## [0.1.0] - 2026-07-06

### Features

- Implement mesoscopic LTM package in a package structure (#1)
- Introduce comprehensive documentation for end users and llms (#5)

### Enhancements

- Implement extended visualization functionalities including animations (#2)

### Documentation

- Improve the structure of the documentation and metrics computation (#6)

### Miscellaneous Tasks

- Set up context and auxiliary means for AI coding assistant
- Add serena for memory management
- Update test action to only run on python 3.11
- Add example script to replicate figures from abmmeso paper (#3)
- Update deployment workflow to be fully automated on tag push including changelog updates (#4)
- Update docs actions
- Increase default buffer size for vehicle injection
- *(release)* V0.1.0
