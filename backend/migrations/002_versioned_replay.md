# 002 工单版本与排班日重放

应用启动时在 `create_all` 之后幂等执行（`src/config/migrate.py`），可重复运行。

- `runs` 增加 `snapshot_id` 列：一次重算钉住的工单版本高水位，页面与下载使用同一批版本。
- 新建 `job_records`：工单版本表。每次导入的每行追加一条，带收到时间，只增不改；`(dataset_id, job_id)` 唯一。
- 新建 `day_estimates`：排班日估算表。`(schedule_day, job_id)` 唯一，估算列算出后不改写；验算列（`verify_*`）随迟到补录与更正实耗在重算时补齐。
- 历史 `datasets` 批次按批次创建时间回填 `job_records`，升级前的旧批次也能参与重放。
