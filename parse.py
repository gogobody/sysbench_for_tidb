#!/usr/bin/env python
# -*- coding:utf-8 -*-

# python sysbench_papapa.py --host=127.0.0.1 --user=hcloud --password=hcloud

import os, sys, re
import click
import time
import xlsxwriter
import re
from collections import namedtuple
from utils import (
    logger,
    run_cmd,
    MySQL,
)


# user variables
class SB(object):
    sc = {
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

    }

    def __init__(self):
        self.bin = b'sysbench'
        self.oltp = self.sc['TESTLIST'][0]
        self.db = self.sc['db']
        self.table_size = self.sc['table_size']
        self.run_time = self.sc['run_time']
        self.tables = self.sc['tables']
        self.threads = self.sc['threads'].get('normal')
        self.report_interval = self.sc['report-interval']
        self.warmup_time = self.sc['warmup-time']
        self.prepare = None
        self.tmp_time = 1
        self.test_interval = 30,  # 100s



sb = SB()
###
# global variables
base_dir = os.path.split(os.path.realpath(__file__))[0]
script = os.path.basename(__file__)

logfile = "%s/%s.log" % (base_dir, script.split('.')[0])
logging = logger(logfile)

subprefix = time.strftime('%Y%m%d_%H%M%S', time.localtime(time.time()))
res_dir = "%s/sysbench_result/%s" % (base_dir, subprefix)


def _run(cmd, display=0):
    try:
        code, out, err = run_cmd(cmd, display)
    except Exception as err:
        logging.error("_run-%s exception, cmd: %s \nerr: %s." % (display, cmd, err))
        return 1, '', err
    logging.info("_run-%s, cmd: %s \ncode: %s \nout: %s \nerr: %s." % (display, cmd, code, out, err))
    return int(code), out, err


def _message(msg, level='info'):
    if level == 'info':
        logging.info(msg)
    else:
        logging.error(msg)
    print(msg)


def init_mysql(host, user, password):
    try:
        h, p = host.split(':')[0], int(host.split(':')[1])
    except Exception as e:
        _message("MySQL host和port验证失败，例如127.0.0.1:3306，退出。")
        return False
    mysql_config = {
        'host': h,
        'port': p,
        'user': user,
        'password': password,
    }
    try:
        mysql = MySQL(mysql_config)
        return mysql
    except Exception as e:
        _message("MySQL服务登录异常: %s，退出。" % e)
        return False


def check_env(host, user, password):
    def _check_sysbench():
        cmd = "which sysbench"
        cs_code, cs_out, cs_err = _run(cmd)
        sb.bin = s_bin = cs_out.decode('utf-8').split(':')[-1].split()[-1].strip()
        if cs_code == 0 and s_bin:
            v_cmd = "%s --version" % s_bin
            v_code, v_out, v_err = _run(v_cmd)
            version = v_out.decode('utf-8').split()[-1]
            if v_code == 0 and version > '1.0':
                # o_cmd = "find / -name %s" % sb.oltp
                # o_code, o_out, o_err = _run(o_cmd)
                # if o_code == 0 and o_out:
                #     sb.oltp = o_out.split()[0]
                # else:
                #     _message("sysbench lua脚本未找到，退出。")
                #     return False
                logging.info("sysbench检查通过。")
                return True
            else:
                _message("sysbench版本检查异常，需要大于1.0版本，退出。")
                return False
        else:
            _message("没有找到sysbench安装路径，确定安装了sysbench软件，退出。")
            return False

    def _check_mysql(_mysql, _sql):
        try:
            check_sql = "show databases"
            _mysql.execute(check_sql)
            cursor = _mysql.getInstance()
            databases = [cursor.fetchall()]
            databases_list = re.findall('(\'.*?\')', str(databases))
            databases_list = [re.sub("'", '', each) for each in databases_list]
            if sb.db in databases_list:
                sb.prepare = 0
                logging.info("MySQL已经存在%s，未执行sql: %s。" % (sb.db, _sql))
                return True
            res = _mysql.execute(_sql)
            if res == 1:
                sb.prepare = 1
                logging.info("MySQL创建%s成功。" % sb.db)
            elif res == 0:
                sb.prepare = 0
                logging.info("MySQL已经存在%s，未执行sql: %s。" % (sb.db, _sql))
            return True
        except Exception as e:
            _message("MySQL创建test db失败，sql: %s, error: %s, 退出。" % (_sql, e))
            return False

    mysql = init_mysql(host, user, password)
    sql = "CREATE DATABASE IF NOT EXISTS %s" % sb.db
    if _check_sysbench() and _check_mysql(mysql, sql):
        _message("环境检查通过，准备压测命令。")
        return True
    else:
        return False


def drop_testdb(host, user, password):
    def _drop_mysql(_mysql, _sql):
        try:
            res = _mysql.execute(_sql)
            if res == 1:
                _message("MySQL删除%s成功。" % (sb.db))
            elif res == 0:
                _message("MySQL中没有%s，未执行sql: %s。" % (sb.db, _sql))
            return True
        except Exception as e:
            _message("MySQL删除test db失败，sql: %s, error: %s, 退出。" % (_sql, e))
            return False

    sql = "DROP DATABASE IF EXISTS %s" % sb.db
    mysql = init_mysql(host, user, password)
    _drop_mysql(mysql, sql)


def sysbench_run(host, user, password):
    h, p = host.split(':')[0], int(host.split(':')[1])
    base_cmd = "{sb_bin} {sb_oltp} ".format(sb_bin=sb.bin, sb_oltp=sb.oltp)
    parameter_opt = "--table_size={sb_ts} --db-driver=mysql --tables={sb_t} --report-interval={sb_report} " \
                    "--warmup-time={sb_warmupt}".format(sb_ts=sb.table_size, sb_t=sb.tables,
                                                        sb_report=sb.report_interval
                                                        , sb_warmupt=sb.warmup_time)
    auth_opt = " --mysql-host={host} --mysql-user={user} --mysql-port={port} --mysql-password={password}".format(host=h,
                                                                                                                 user=user,
                                                                                                                 port=p,
                                                                                                                 password=password
                                                                                                                 )

    def _sb_run():
        if not os.path.isdir(res_dir):
            os.makedirs(res_dir)
        _message("将要开始压力测试，压测场景%s，并发%s，结果输出路径%s。" % (sb.oltp, sb.threads, res_dir))
        for t in sb.threads:
            _message("并发%s，持续时间%ss，run压测即将开始。" % (t, sb.run_time))
            run_opt = " --threads={threads} --time={time}".format(threads=t, time=sb.run_time)
            export_file = "%s/%s-%s-times%s" % (res_dir, sb.oltp, t, sb.tmp_time)
            cmd = base_cmd + parameter_opt + run_opt + auth_opt + ' run > ' + export_file
            _message("CMD: {}".format(cmd))
            code, out, err = _run(cmd, sb.run_time)
            if code == 0:
                _message("并发%s，run压测已经完成。" % t)
            else:
                _message("run压测失败，请查看日志，退出。")
                return False
        return True

    def _sb_prepare():
        cmd = base_cmd + parameter_opt + auth_opt + ' prepare'
        code, out, err = _run(cmd, 1)
        if code == 0:
            _message("perpare测试数据完成。")
            return True
        else:
            _message("perpare测试数据失败，请查看日志，退出。")
            return False

    if sb.prepare == 1:
        _message("准备perpare测试数据，%s * %s。" % (sb.tables, sb.table_size))
        if not _sb_prepare():
            return False
    elif sb.prepare == 0:
        _message("测试数据已经存在，不在执行prepare命令。")
    if _sb_run():
        _message("sysbench执行压测全部完成。")
        return True
    else:
        return False


def get_excl():
    def get_normal_data(line_):
        return line_.split()[-1]

    def get_re_data(line_):
        res_ = re.search(r'\((.*) per sec.\)', line)
        return res_.group(1)

    logging.info("start get_excl.")
    oltp_list = set()
    for maindir, subdir, file_name_list in os.walk(res_dir):
        for file_name in file_name_list:
            if not file_name.startswith('result'):
                olpt, thread, cishu = file_name.split('-')
                oltp_list.add(olpt)
    for oltp_name in oltp_list:
        excel_file = '%s/result_%s.xlsx' % (res_dir, oltp_name)
        workbook = xlsxwriter.Workbook(excel_file)
        worksheet = workbook.add_worksheet()
        bold = workbook.add_format({'bold': 1})
        data_list = []
        left_list, read_list, write_list, other_list, total_list, tps_list, qps_list, eps_list, late_min, late_avg, late_max, late_95th = [], [], [], [], [], [], [], [], [], [], [], []
        count = 0

        for maindir, subdir, file_name_list in os.walk(res_dir):
            count = len(file_name_list) + 1
            new_file_name_list = []
            for f in file_name_list:
                if f.startswith('result'):
                    continue
                olpt, _, _ = f.split('-')
                if olpt != oltp_name:
                    continue
                new_file_name_list.append(f)
            new_file_name_list.sort(key=lambda x: int(x.split('-')[1]))
            for file_name in new_file_name_list:
                if not re.match('result', file_name):
                    absfname = os.path.abspath(os.path.join(maindir, file_name))
                    olpt, thread, cishu = file_name.split('-')
                    check_count = 0
                    with open(absfname, 'r') as f:
                        lines = f.readlines()
                        for line in lines:
                            line = line.strip()
                            if line.startswith('read:'):
                                read_list.append(int(get_normal_data(line)))
                                check_count += 1
                            elif line.startswith('write:'):
                                write_list.append(int(get_normal_data(line)))
                                check_count += 1
                            elif line.startswith('other:'):
                                other_list.append(int(get_normal_data(line)))
                                check_count += 1
                            elif line.startswith('total:'):
                                total_list.append(int(get_normal_data(line)))
                                check_count += 1
                            elif line.startswith('transactions:'):
                                tps_list.append(float(get_re_data(line)))
                                check_count += 1
                            elif line.startswith('queries:'):
                                qps_list.append(float(get_re_data(line)))
                                check_count += 1
                            elif line.startswith('events/s (eps):'):
                                eps_list.append(float(get_normal_data(line)))
                                check_count += 1
                            elif line.startswith('min:'):
                                late_min.append(float(get_normal_data(line)))
                                check_count += 1
                            elif line.startswith('avg:'):
                                late_avg.append(float(get_normal_data(line)))
                                check_count += 1
                            elif line.startswith('max:'):
                                late_max.append(float(get_normal_data(line)))
                                check_count += 1
                            elif line.startswith('95th percentile:'):
                                late_95th.append(float(get_normal_data(line)))
                                check_count += 1
                    if check_count is not 11:
                        _message('file {} not complete!check count {} '.format(file_name, check_count))
                        return False
                    left_list.append("%s" % thread)

        if not tps_list or not qps_list:
            _message("去读sysbench结果文件 {} 失败，退出。".format(excel_file))
            return False

        data_list.append(left_list)
        data_list.append(tps_list)
        data_list.append(qps_list)
        data_list.append(eps_list)
        data_list.append(read_list)
        data_list.append(write_list)
        data_list.append(other_list)
        data_list.append(total_list)
        data_list.append(late_min)
        data_list.append(late_avg)
        data_list.append(late_max)
        data_list.append(late_95th)

        # write excel
        head_list = ['Indicator', 'TPS', 'QPS', 'EPS', 'read', 'write', 'other', 'total', 'late_min', 'late_avg',
                     'late_max', 'late_95th']

        worksheet.write_row('A1', head_list, bold)
        if len(data_list) > 27:
            _message("excl的列数太大，不支持生成excl文件，退出。")
            return False
        li = [chr(i) for i in range(ord("A"), ord("Z") + 1)]
        column_list = ["%s2" % c for c in li]

        for i in range(len(data_list)):
            worksheet.write_column(column_list[i], data_list[i])
        # add chart
        chart_col = workbook.add_chart({'type': 'line'})

        chart_col.add_series({
            'name': '=Sheet1!$B$1',
            'categories': '=Sheet1!$A$2:$A$%s' % count,
            'values': '=Sheet1!$B$2:$B$%s' % count,
            'line': {'color': 'gray'},
        })
        chart_col.add_series({
            'name': '=Sheet1!$C$1',
            'categories': '=Sheet1!$A$2:$A$%s' % count,
            'values': '=Sheet1!$C$2:$C$%s' % count,
            'line': {'color': 'lime'},
        })

        chart_col.set_title({'name': 'performance benchmark test'})
        chart_col.set_x_axis({'name': 'concurrency'})
        chart_col.set_y_axis({'name': 'number'})

        chart_col.set_style(1)
        worksheet.insert_chart('A10', chart_col, {'x_offset': 25, 'y_offset': 10})

        workbook.close()
        _message("已经生成excl文件，%s。" % excel_file)
    return True


@click.command()
@click.option('--host', required=True, type=str, help='host_ip:mysql_port, ex: 127.0.0.1:3306.')
@click.option('--user', required=True, type=str, help='login MySQL user name.')
@click.option('--password', required=True, type=str, help='login MySQL password.')
@click.option('--times', required=False, type=str, help='运行次数.')
@click.argument('drop', nargs=1, default=0)
def main(host, user, password, times, drop):
    if not times:
        times = 1
    if drop:
        drop_testdb(host, user, password)
        sys.exit(0)
    if not check_env(host, user, password):
        _message("环境检查失败，请查看日志，退出。")
        sys.exit(0)
    for j in SB.sc.get('TESTLIST', []):
        sb.oltp = j
        for i in range(int(times)):
            sb.tmp_time = i + 1  # 第 i + 1 次测试开始
            _message("##{} 第 {} 次测试开始".format(j, i + 1))
            logging.info("##{} 第 {} 次测试开始".format(j, i + 1))
            if not sysbench_run(host, user, password):
                _message("执行sysbench命令失败，请查看日志，退出。")
                sys.exit(0)
            time.sleep(sb.report_interval)
    if not get_excl():
        _message("整理结果出现问题，请查看日志和%s的sysbench的输出，退出。" % res_dir)
        sys.exit(0)
    _message("压力测试已经全部结束。")


if __name__ == "__main__":
    logging.info("========%s starting========" % script)
    main()
