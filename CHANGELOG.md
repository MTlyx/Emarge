# Changelog

## [v2.5] - 2025-05-07

### Fixed
- Fix firefox crash when opening it
- Fix schedule on ubuntu

## [v2.4] - 2025-03-19
    
### Added
- The possibility to have a notification on your phone with ntfy when you emerge
- The possibility to only get notification on your phone
- Check each morning if their is an update
- Logs the error
- Support moodle on english

### Changed
- Use the geckodriver from the docker image
- Emerge from 5-10 min
- To check for new update

### Fixed
- Fix the delay to emarge on 1 min
- Optimize docker build

## [v2.3] - 2025-03-05

### Added
- Random user agent on linux
- Request the API to emarge at 7h
- Can only emarge between 8h and 18h

### Changed
- Switch to BeautifulSoup

### Fixed
- Wierd bug on the reset part
- TimeZone filtering on API
- Bot stop restarting himself

## [v2.2] - 2025-02-26

### Added
- Blacklist used from the environment variables

### Changed
- Emerge from 15-25 min

### Fixed
- Fix emerge keep past event

## [v2.1] - 2025-02-24

### Added
- Integration with PlanningSup API for automatic schedule fetching
- Event filtering logic for special activities
- Random attendance check-in delays (5-15 minutes)
- Daily schedule refresh at midnight
- Changelog file
- FORMATION variable

### Changed
- Moved from static to dynamic scheduling
- Optimized API calls by checking weekdays first
- Removed CourseID and AttendanceID specification
- Removed SEMESTRE specification
- Sort list of time to emarge

### Fixed
- Resolved Selenium timing issues with additional delays
- Resolved schedule timing issues
- Corrected timezone discrepancies in schedule fetching
- Adjusted some timing with wooden connection like eduroam

## [v2.0] - 2024-12-15

### Added
- Docker containerization support
- Environment variable configuration in the docker-compose
- Weekend detection
- Colored console output

### Changed
- Automated browser interactions

### Fixed
- Browser compatibility issues
- Location of log files
- Support for Windows, Mac and VPS 

## [v1.0] - 2024-10-01

### Added
- Initial release
- Manual attendance tracking
- Basic web interface interaction
- Command-line interface
- Crontab possibility
- .env file