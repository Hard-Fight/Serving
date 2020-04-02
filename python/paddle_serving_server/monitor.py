# Copyright (c) 2020 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Usage:
    Start monitor with one line command
    Example:
        python -m paddle_serving_server.monitor
"""
import os
import time
import argparse
import commands
import datetime
import shutil
import tarfile
import logging

_LOGGER = logging.getLogger(__name__)


class Monitor(object):
    '''
    Monitor base class. It is used to monitor the remote model, pull and update the local model.
    '''

    def __init__(self, interval):
        self._remote_path = None
        self._remote_model_name = None
        self._remote_donefile_name = None
        self._local_path = None
        self._local_model_name = None
        self._local_timestamp_file = None
        self._interval = interval
        self._remote_donefile_timestamp = None
        self._local_tmp_path = None
        self._unpacked_filename = None

    def set_remote_path(self, remote_path):
        self._remote_path = remote_path

    def set_remote_model_name(self, model_name):
        self._remote_model_name = model_name

    def set_remote_donefile_name(self, donefile_name):
        self._remote_donefile_name = donefile_name

    def set_local_path(self, local_path):
        self._local_path = local_path

    def set_local_model_name(self, model_name):
        self._local_model_name = model_name

    def set_local_timestamp_file(self, timestamp_file):
        self._local_timestamp_file = timestamp_file

    def set_local_tmp_path(self, tmp_path):
        self._local_tmp_path = tmp_path

    def set_unpacked_filename(self, unpacked_filename):
        self._unpacked_filename = unpacked_filename

    def _check_param_help(self, param_name, param_value):
        return "Please check the {}({}) parameter.".format(param_name,
                                                           param_value)

    def _check_params(self, params):
        for param in params:
            if getattr(self, param, None) is None:
                raise Exception('{} not set.'.format(param))

    def _print_params(self, params_name):
        self._check_params(params_name)
        for name in params_name:
            _LOGGER.info('{}: {}'.format(name, getattr(self, name)))

    def _decompress_model_file(self, local_tmp_path, model_name,
                               unpacked_filename):
        if unpacked_filename is None:
            _LOGGER.debug('remote file({}) is already unpacked.'.format(
                model_name))
            return model_name
        tar_model_path = os.path.join(local_tmp_path, model_name)
        if not tarfile.is_tarfile(tar_model_path):
            raise Exception('not a tar packaged file type. {}'.format(
                self._check_param_help('remote_model_name', model_name)))
        try:
            _LOGGER.info('unpack remote file({}).'.format(model_name))
            tar = tarfile.open(tar_model_path)
            tar.extractall(local_tmp_path)
            tar.close()
        except:
            raise Exception(
                'Decompressing failed, maybe no disk space left. {}'.foemat(
                    self._check_param_help('local_tmp_path', local_tmp_path)))
        finally:
            os.remove(tar_model_path)
            _LOGGER.debug('remove packed file({}).'.format(model_name))
            _LOGGER.info('using unpacked filename: {}.'.format(
                unpacked_filename))
            if not os.path.exists(unpacked_filename):
                raise Exception('file not exist. {}'.format(
                    self._check_param_help('unpacked_filename',
                                           unpacked_filename)))
            return unpacked_filename

    def run(self):
        '''
        Monitor the remote model by polling and update the local model.
        '''
        params = [
            '_remote_path', '_remote_model_name', '_remote_donefile_name',
            '_local_model_name', '_local_path', '_local_timestamp_file',
            '_local_tmp_path', '_interval'
        ]
        self._print_params(params)
        if not os.path.exists(self._local_tmp_path):
            _LOGGER.info('mkdir: {}'.format(self._local_tmp_path))
            os.makedirs(self._local_tmp_path)
        while True:
            [flag, timestamp] = self._exist_remote_file(
                self._remote_path, self._remote_donefile_name,
                self._local_tmp_path)
            if flag:
                if self._remote_donefile_timestamp is None or \
                        timestamp != self._remote_donefile_timestamp:
                    _LOGGER.info('doneilfe({}) changed.'.format(
                        self._remote_donefile_name))
                    self._remote_donefile_timestamp = timestamp
                    self._pull_remote_dir(self._remote_path,
                                          self._remote_model_name,
                                          self._local_tmp_path)
                    _LOGGER.info('pull remote model({}).'.format(
                        self._remote_model_name))
                    unpacked_filename = self._decompress_model_file(
                        self._local_tmp_path, self._remote_model_name,
                        self._unpacked_filename)
                    self._update_local_model(
                        self._local_tmp_path, unpacked_filename,
                        self._local_path, self._local_model_name)
                    _LOGGER.info('update local model({}).'.format(
                        self._local_model_name))
                    self._update_local_donefile(self._local_path,
                                                self._local_model_name,
                                                self._local_timestamp_file)
                    _LOGGER.info('update model timestamp({}).'.format(
                        self._local_timestamp_file))
            else:
                _LOGGER.info('remote({}) has no donefile.'.format(
                    self._remote_path))
            _LOGGER.info('sleep {}s.'.format(self._interval))
            time.sleep(self._interval)

    def _exist_remote_file(self, path, filename, local_tmp_path):
        raise Exception('This function must be inherited.')

    def _pull_remote_dir(self, remote_path, dirname, local_tmp_path):
        raise Exception('This function must be inherited.')

    def _update_local_model(self, local_tmp_path, remote_model_name, local_path,
                            local_model_name):
        tmp_model_path = os.path.join(local_tmp_path, remote_model_name)
        local_model_path = os.path.join(local_path, local_model_name)
        cmd = 'cp -r {}/* {}'.format(tmp_model_path, local_model_path)
        _LOGGER.debug('update model cmd: {}'.format(cmd))
        if os.system(cmd) != 0:
            raise Exception('update local model failed.')

    def _update_local_donefile(self, local_path, local_model_name,
                               local_timestamp_file):
        donefile_path = os.path.join(local_path, local_model_name,
                                     local_timestamp_file)
        cmd = 'touch {}'.format(donefile_path)
        _LOGGER.debug('update timestamp cmd: {}'.format(cmd))
        if os.system(cmd) != 0:
            raise Exception('update local donefile failed.')


class AFSMonitor(Monitor):
    ''' AFS Monitor(by hadoop-client). '''

    def __init__(self,
                 hadoop_bin,
                 hadoop_host=None,
                 hadoop_ugi=None,
                 interval=10):
        super(AFSMonitor, self).__init__(interval)
        self._hadoop_bin = hadoop_bin
        self._hadoop_host = hadoop_host
        self._hadoop_ugi = hadoop_ugi
        self._print_params(['_hadoop_bin', '_hadoop_host', '_hadoop_ugi'])
        self._cmd_prefix = '{} fs '.format(self._hadoop_bin)
        if self._hadoop_host and self._hadoop_ugi:
            self._cmd_prefix += '-D fs.default.name={} -D hadoop.job.ugi={} '.format(
                self._hadoop_host, self._hadoop_ugi)
        _LOGGER.info('AFS prefix cmd: {}'.format(self._cmd_prefix))

    def _exist_remote_file(self, path, filename, local_tmp_path):
        remote_filepath = os.path.join(path, filename)
        cmd = '{} -ls {} 2>/dev/null'.format(self._cmd_prefix, remote_filepath)
        _LOGGER.debug('check cmd: {}'.format(cmd))
        [status, output] = commands.getstatusoutput(cmd)
        _LOGGER.debug('resp: {}'.format(output))
        if status == 0:
            [_, _, _, _, _, mdate, mtime, _] = output.split('\n')[-1].split()
            timestr = mdate + mtime
            return [True, timestr]
        else:
            return [False, None]

    def _pull_remote_dir(self, remote_path, dirname, local_tmp_path):
        # remove old file before pull remote dir
        local_dirpath = os.path.join(local_tmp_path, dirname)
        if os.path.exists(local_dirpath):
            _LOGGER.info('remove old temporary model file({}).'.format(dirname))
            shutil.rmtree(local_dirpath)
        remote_dirpath = os.path.join(remote_path, dirname)
        cmd = '{} -get {} {} 2>/dev/null'.format(self._cmd_prefix,
                                                 remote_dirpath, local_dirpath)
        _LOGGER.debug('pull cmd: {}'.format(cmd))
        if os.system(cmd) != 0:
            raise Exception('pull remote dir failed. {}'.format(
                self._check_param_help('remote_model_name', dirname)))


class HDFSMonitor(Monitor):
    ''' HDFS Monitor. '''

    def __init__(self, hdfs_bin, interval=10):
        super(HDFSMonitor, self).__init__(interval)
        self._hdfs_bin = hdfs_bin
        self._print_params(['_hdfs_bin'])
        self._prefix_cmd = '{} dfs '.format(self._hdfs_bin_path)
        _LOGGER.info('HDFS prefix cmd: {}'.format(self._cmd_prefix))

    def _exist_remote_file(self, path, filename, local_tmp_path):
        remote_filepath = os.path.join(path, filename)
        cmd = '{} -stat "%Y" {}'.format(self._prefix_cmd, remote_filepath)
        _LOGGER.debug('check cmd: {}'.format(cmd))
        [status, timestamp] = commands.getstatusoutput(cmd)
        _LOGGER.debug('resp: {}'.format(output))
        if status == 0:
            return [True, timestamp]
        else:
            return [False, None]

    def _pull_remote_dir(self, remote_path, dirname, local_tmp_path):
        remote_dirpath = os.path.join(remote_path, dirname)
        cmd = '{} -get -f {} {}'.format(self._prefix_cmd, remote_dirpath,
                                        local_tmp_path)
        _LOGGER.debug('pull cmd: {}'.format(cmd))
        if os.system(cmd) != 0:
            raise Exception('pull remote dir failed. {}'.format(
                self._check_param_help('remote_model_name', dirname)))


class FTPMonitor(Monitor):
    ''' FTP Monitor. '''

    def __init__(self, host, port, username="", password="", interval=10):
        super(FTPMonitor, self).__init__(interval)
        import ftplib
        self._ftp = ftplib.FTP()
        self._ftp_host = host
        self._ftp_port = port
        self._ftp_username = username
        self._ftp_password = password
        self._ftp.connect(self._ftp_host, self._ftp_port)
        self._ftp.login(self._ftp_username, self._ftp_password)
        self._print_params(
            ['_ftp_host', '_ftp_port', '_ftp_username', '_ftp_password'])

    def _exist_remote_file(self, path, filename, local_tmp_path):
        import ftplib
        try:
            _LOGGER.debug('cwd: {}'.format(path))
            self._ftp.cwd(path)
            timestamp = self._ftp.voidcmd('MDTM {}'.format(filename))[4:].strip(
            )
            return [True, timestamp]
        except ftplib.error_perm:
            _LOGGER.debug('remote file({}) not exist.'.format(filename))
            return [False, None]

    def _download_remote_file(self,
                              remote_path,
                              remote_filename,
                              local_tmp_path,
                              overwrite=True):
        local_fullpath = os.path.join(local_tmp_path, remote_filename)
        if not overwrite and os.path.isfile(fullpath):
            return
        else:
            with open(local_fullpath, 'wb') as f:
                _LOGGER.debug('cwd: {}'.format(path))
                self._ftp.cwd(remote_path)
                _LOGGER.debug('download remote file({})'.format(remote_path))
                self._ftp.retrbinary('RETR {}'.format(remote_filename), f.write)

    def _download_remote_files(self,
                               remote_path,
                               remote_dirname,
                               local_tmp_path,
                               overwrite=True):
        import ftplib
        remote_dirpath = os.path.join(remote_path, remote_dirname)
        # Check whether remote_dirpath is a file or a folder
        try:
            _LOGGER.debug('cwd: {}'.format(remote_dirpath))
            self._ftp.cwd(remote_dirpath)
            _LOGGER.debug('{} is folder.'.format(remote_dirname))

            local_dirpath = os.path.join(local_tmp_path, remote_dirname)
            if not os.path.exists(local_dirpath):
                _LOGGER.info('mkdir: {}'.format(local_dirpath))
                os.mkdir(local_dirpath)

            output = []
            self._ftp.dir(output.append)
            for line in output:
                [attr, _, _, _, _, _, _, _, name] = line.split()
                if attr[0] == 'd':
                    self._download_remote_files(
                        os.path.join(remote_path, remote_dirname), name,
                        os.path.join(local_tmp_path, remote_dirname), overwrite)
                else:
                    self._download_remote_file(remote_dirname, name,
                                               local_tmp_path, overwrite)
        except ftplib.error_perm:
            _LOGGER.debug('{} is file.'.format(remote_dirname))
            self._download_remote_file(remote_path, remote_dirname,
                                       local_tmp_path, overwrite)
            return

    def _pull_remote_dir(self, remote_path, dirname, local_tmp_path):
        self._download_remote_files(
            remote_path, dirname, local_tmp_path, overwrite=True)


class GeneralMonitor(Monitor):
    ''' General Monitor. '''

    def __init__(self, host, interval=10):
        super(GeneralMonitor, self).__init__(interval)
        self._general_host = host
        self._print_params(['_general_host'])

    def _get_local_file_timestamp(self, filename):
        return os.path.getmtime(filename)

    def _exist_remote_file(self, path, filename, local_tmp_path):
        remote_filepath = os.path.join(path, filename)
        url = '{}/{}'.format(self._general_host, remote_filepath)
        _LOGGER.debug('remote file url: {}'.format(url))
        cmd = 'wget -N -P {} {} &>/dev/null'.format(local_tmp_path, url)
        _LOGGER.debug('wget cmd: {}'.format(cmd))
        if os.system(cmd) != 0:
            _LOGGER.debug('remote file({}) not exist.'.format(filename))
            return [False, None]
        else:
            _LOGGER.debug('download remote file({}).'.format(filename))
            timestamp = self._get_local_file_timestamp(
                os.path.join(local_tmp_path, filename))
            return [True, timestamp]

    def _pull_remote_dir(self, remote_path, dirname, local_tmp_path):
        remote_dirpath = os.path.join(remote_path, dirname)
        url = '{}/{}'.format(self._general_host, remote_dirpath)
        _LOGGER.debug('remote file url: {}'.format(url))
        cmd = 'wget -nH -r -P {} {} &>/dev/null'.format(local_tmp_path, url)
        _LOGGER.debug('wget cmd: {}'.format(cmd))
        if os.system(cmd) != 0:
            raise Exception('pull remote dir failed. {}'.format(
                self._check_param_help('remote_model_name', dirname)))


def parse_args():
    ''' parse args. '''
    parser = argparse.ArgumentParser(description="Monitor")
    parser.add_argument(
        "--type", type=str, default='general', help="Type of remote server")
    parser.add_argument(
        "--remote_path", type=str, required=True, help="Remote path")
    parser.add_argument(
        "--remote_model_name",
        type=str,
        required=True,
        help="Remote model name")
    parser.add_argument(
        "--remote_donefile_name",
        type=str,
        required=True,
        help="Remote donefile name")
    parser.add_argument(
        "--local_path", type=str, required=True, help="Local path")
    parser.add_argument(
        "--local_model_name", type=str, required=True, help="Local model name")
    parser.add_argument(
        "--local_timestamp_file",
        type=str,
        default='fluid_time_file',
        help="Local timestamp file name(fluid_time_file in model file)")
    parser.add_argument(
        "--local_tmp_path",
        type=str,
        default='_serving_monitor_tmp',
        help="Local tmp path")
    parser.add_argument(
        "--unpacked_filename",
        type=str,
        default=None,
        help="If the model of the remote production is a packaged file, the unpacked file name should be set. Currently, only tar packaging format is supported."
    )
    parser.add_argument(
        "--interval", type=int, default=10, help="Time interval")
    # general monitor
    parser.add_argument(
        "--general_host", type=str, help="Host of general remote server")
    # hdfs monitor
    parser.add_argument("--hdfs_bin", type=str, help="Hdfs binary file path")
    # ftp monitor
    parser.add_argument("--ftp_host", type=str, help="Host of ftp")
    parser.add_argument("--ftp_port", type=int, help="Port of ftp")
    parser.add_argument(
        "--ftp_username", type=str, default='', help="Username of ftp")
    parser.add_argument(
        "--ftp_password", type=str, default='', help="Password of ftp")
    # afs monitor
    parser.add_argument(
        "--hadoop_bin", type=str, help="Hadoop_bin_path for afs")
    parser.add_argument(
        "--hadoop_host", type=str, default=None, help="Hadoop_host for afs")
    parser.add_argument(
        "--hadoop_ugi", type=str, default=None, help="Hadoop_ugi for afs")
    return parser.parse_args()


def get_monitor(mtype):
    """ generator monitor instance.

    Args:
        mtype: type of monitor

    Returns:
        monitor instance.
    """
    if mtype == 'ftp':
        return FTPMonitor(
            args.ftp_host,
            args.ftp_port,
            username=args.ftp_username,
            password=args.ftp_password,
            interval=args.interval)
    elif mtype == 'hdfs':
        return HDFSMonitor(args.hdfs_bin, interval=args.interval)
    elif mtype == 'general':
        return GeneralMonitor(args.general_host, interval=args.interval)
    elif mtype == 'afs':
        return AFSMonitor(
            args.hadoop_bin,
            args.hadoop_host,
            args.hadoop_ugi,
            interval=args.interval)
    else:
        raise Exception('unsupport type.')


def start_monitor(monitor, args):
    monitor.set_remote_path(args.remote_path)
    monitor.set_remote_model_name(args.remote_model_name)
    monitor.set_remote_donefile_name(args.remote_donefile_name)
    monitor.set_local_path(args.local_path)
    monitor.set_local_model_name(args.local_model_name)
    monitor.set_local_timestamp_file(args.local_timestamp_file)
    monitor.set_local_tmp_path(args.local_tmp_path)
    monitor.set_unpacked_filename(args.unpacked_filename)
    monitor.run()


if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M',
        level=logging.INFO)
    args = parse_args()
    monitor = get_monitor(args.type)
    start_monitor(monitor, args)
