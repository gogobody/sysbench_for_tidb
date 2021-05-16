# sysbench_for_tidb
sysbench test script for tidb

默认的配置文件在 parse.py 里面
```angular2html
'db': "sbtest",
'table_size': 1000000,
'tables': 32,
'run_time': 600,
'report-interval': 10,
'warmup-time': 300,
'threads': {
    'normal': [4, 8, 16, 32, 64],  #
},
'TESTLIST': ['oltp_point_select', 'oltp_update_index', 'oltp_read_only'],

```

times 是 TESTLIST 列表里的测试项，对应的 threads ，每一种线程测试多少次
```angular2html
python parse.py --host=127.0.0.1 --user=hcloud --password=hcloud --times=5
```
