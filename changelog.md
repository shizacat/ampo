# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Types of changes: Added, Changed, Deprecated, Removed, Fixed, Security

## [Unreleased]

- Added to index new option - 'commit_quorum'. See [docs](https://www.mongodb.com/docs/manual/reference/command/createIndexes/#std-label-createIndexes-cmd-commitQuorum).
- Added periodic checking to the method create indexes.
- Method 'get_all' don't compatible with previous versions! Update method 'get_all' to support additional options. Options: filter, sort, limit, skip.
- Add property 'id' to WorkerCollection.
- Revalidate fields is enabled every time they are updated. The 'validate_assignment' parameter is set to True.
- The default value of the field is now validated. The 'validate_default' parameter is set to True.


## [0.2.7] - 2024-07-10

### Added

- Add mechanism - lock-record


## [0.2.6] - 2024-04-17

### Changed

- The 'update_expiration_value' method has been updated to allow for multiple calls without error.


## [0.2.5] - 2024-04-17

### Added

- The method 'expiration_index_skip' was added

### Changed

- The method 'update_expiration_value' was renamed to 'expiration_index_update'


## [0.2.4] - 2024-04-17

### Added

- The Method 'count' was added


## [0.2.3] - 2024-04-01

### Changed

- The method 'db.AMPODatabase.get_db' is not longer a 'classmethod'

### Added

- The Method 'delete'


## [0.2.2] - 2024-02-17

### Added
- Set version from tag


## [0.2.1] - 2024-02-17

### Added

- The 'update_expiration_value' method has been added for worker.
- Was changed behavior for TTL index.


## [0.2.0] - 2023-11-01

### Added

- Option ORMConfig.orm_bson_codec_options - This options will apply on the collection every time, when the collection is returned


## [0.0.0] - [date] - Example

### Removed
### Changed
### Fixed
### Added