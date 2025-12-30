# CL_SERVER


This repository acts as a **workspace / umbrella project** that aggregates multiple independent repositories for cl_server using **Git submodules**. 

##  Status
### Micro Services
#### Auth service

TBD

#### Store service

TBD

#### Compute Service

TBD

### Tools 
####  Media Processing and Machine Learning Tools

TBD

### SDK
#### Python Client

TBD

#### Dart Client

TBD

### Demo Apps

### Python CLI App

TBD

### Dart CLI App

TBD

### Flutter App

TBD




### Submodule Mapping

| Repository | Local Path |
|-----------|-----------|
| `git@github.com:cloudonlanapps/cl_server_dockers.git` | `dockers` |
| `git@github.com:cloudonlanapps/cl_server_auth_service.git` | `services/auth` |
| `git@github.com:cloudonlanapps/cl_server_compute_service.git` | `services/compute` |
| `git@github.com:cloudonlanapps/cl_server_store_service.git` | `services/store` |
| `git@github.com:cloudonlanapps/cl_server_shared.git` | `services/shared` |
| `git@github.com:cloudonlanapps/cl_server_sdk_python.git` | `clients/python` |
| `git@github.com:cloudonlanapps/cl_server_sdk_dart.git` | `clients/dart` |

Command

```bash
git submodule add -b main git@github.com:cloudonlanapps/cl_server_dockers.git dockers
git submodule add -b main git@github.com:cloudonlanapps/cl_server_auth_service.git services/auth
git submodule add -b main git@github.com:cloudonlanapps/cl_server_compute_service.git services/compute
git submodule add -b main git@github.com:cloudonlanapps/cl_server_store_service.git services/store
git submodule add -b main git@github.com:cloudonlanapps/cl_server_shared.git services/shared
git submodule add -b main git@github.com:cloudonlanapps/cl_server_sdk_python.git clients/python
git submodule add -b main git@github.com:cloudonlanapps/cl_server_sdk_dart.git clients/dart
```


### Cloning the Workspace

To clone this repository **with all submodules**:

```bash
git clone --recurse-submodules git@github.com:cloudonlanapps/cl_server.git
```

If already cloned:

```bash
git submodule update --init --recursive
```

Update a single submodule:

```bash
git submodule update --remote services/auth
```


### Keeping Submodules in Sync 

All submodules are configured to track the `main` branch.

To update **all submodules** to the latest `main`:

```bash
git submodule update --remote --merge
git commit -am "Update submodules to latest main"
```


