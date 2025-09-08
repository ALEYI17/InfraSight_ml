# Data Schema: `audit.resource_events`

This dataset contains **resource usage events** collected from processes and containers.  
The table is stored in **ClickHouse** with a `MergeTree` engine and ordered by `wall_time_ms`.

## 📑 Table Definition

```sql
CREATE TABLE IF NOT EXISTS audit.resource_events (
  pid UInt32,
  comm String,

  uid UInt32,
  gid UInt32,
  ppid UInt32,
  user_pid UInt32,
  user_ppid UInt32,
  cgroup_id UInt64,
  cgroup_name String,
  user String,

  cpu_ns UInt64,
  user_faults UInt64,
  kernel_faults UInt64,
  vm_mmap_bytes UInt64,
  vm_munmap_bytes UInt64,
  vm_brk_grow_bytes UInt64,
  vm_brk_shrink_bytes UInt64,
  bytes_written UInt64,
  bytes_read UInt64,
  isActive UInt32,

  wall_time_dt DateTime64(3),
  wall_time_ms Int64,

  container_id String,
  container_image String,
  container_labels_json JSON
) ENGINE = MergeTree()
ORDER BY wall_time_ms;
````

## 📋 Field Descriptions

| Column                  | Type          | Description                                                             |
| ----------------------- | ------------- | ----------------------------------------------------------------------- |
| `pid`                   | UInt32        | Process ID                                                              |
| `comm`                  | String        | Command / executable name                                               |
| `uid`                   | UInt32        | User ID of the process owner                                            |
| `gid`                   | UInt32        | Group ID of the process owner                                           |
| `ppid`                  | UInt32        | Parent process ID                                                       |
| `user_pid`              | UInt32        | User namespace PID                                                      |
| `user_ppid`             | UInt32        | User namespace PPID                                                     |
| `cgroup_id`             | UInt64        | Cgroup identifier                                                       |
| `cgroup_name`           | String        | Name of the cgroup                                                      |
| `user`                  | String        | Username of the process owner                                           |
| `cpu_ns`                | UInt64        | CPU time consumed in nanoseconds                                        |
| `user_faults`           | UInt64        | Page faults in user space                                               |
| `kernel_faults`         | UInt64        | Page faults in kernel space                                             |
| `vm_mmap_bytes`         | UInt64        | Bytes mapped into virtual memory                                        |
| `vm_munmap_bytes`       | UInt64        | Bytes unmapped from virtual memory                                      |
| `vm_brk_grow_bytes`     | UInt64        | Bytes allocated by heap expansion (`brk`)                               |
| `vm_brk_shrink_bytes`   | UInt64        | Bytes released by heap shrink (`brk`)                                   |
| `bytes_written`         | UInt64        | Bytes written to storage                                                |
| `bytes_read`            | UInt64        | Bytes read from storage                                                 |
| `isActive`              | UInt32        | Process state flag (e.g., 1 = active, 0 = inactive)                     |
| `wall_time_dt`          | DateTime64(3) | Wall clock timestamp with millisecond precision                         |
| `wall_time_ms`          | Int64         | Wall clock timestamp in milliseconds (used for ordering in `MergeTree`) |
| `container_id`          | String        | Container ID (if running inside a container)                            |
| `container_image`       | String        | Container image name                                                    |
| `container_labels_json` | JSON          | Container metadata labels in JSON format                                |


## 🔒 Notes on Data Privacy

* This dataset may include **process names, usernames, and container details**.
* Do **not** commit full raw exports to GitHub. Instead:

  * Share only the schema (this file).
  * Provide small, **synthetic samples** if needed.
  * Keep real logs in `.gitignore`.

