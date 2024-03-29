#!/usr/bin/python3
"""
Python3 script for eliminating inmail issues
Requirements: subprocess, in_place, time, sys
Input: None
Author: Shivakumar Bommakanti
Date: 04-26-2023
"""
import subprocess
import sys
import time
import logging
import fileinput


def run_commands(commands):
    """Runs unix commands using subprocess module

    Args:
        commands (list): list of commands to execute

    Returns:
        stdout: output of the commands
        stderr: standard error if any
    """
    process = subprocess.Popen("/bin/bash", shell=True, universal_newlines=True,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    for command in commands:
        command += "\n"
        process.stdin.write(command)
    process.stdin.flush()
    stdout, stderr = process.communicate()
    process.stdin.close()
    return stdout, stderr


def get_hostname_new():
    """Gets the hostname from predefined commands new/updated

    Returns:
        hostname: string
    """
    hostname = ""
    stdout, stderr = run_commands(
        ["ls /usr/local/neolane/nl*/conf/config*xml | grep -v default | cut -d. -f1 | cut -d'-' -f2"])
    if stderr:
        logger.exception("error in fetching hostname")
    else:
        hostnames = stdout.split("\n")
        if(len(hostnames) > 1):
            stdout = hostnames[0]
        hostname = stdout.replace('\n', '').replace('\t', '').replace(' ', '')

    return hostname


def get_hostname():
    """Gets the hostname from predefined commands

    Returns:
        hostname: string
    """
    hostname = ""
    stdout, stderr = run_commands(
        ["grep -il 'true' /usr/local/neolane/nl*/conf/config-*.xml | grep -v seczo | grep -v default |  awk -F'config-' '{print $2}' | sed -re 's/.{4}$//'"])
    if stderr:
        logger.exception("error in fetching hostname")
    else:
        hostname = stdout.replace('\n', '').replace('\t', '').replace(' ', '')

    return hostname


def get_db_name():
    """Gets the database name from predefined commands

    Returns:
        db name: string
    """
    dbname = ""
    stdout, stderr = run_commands(
        ["cat /usr/local/neolane/nl*/conf/config-*.xml | grep db | grep login | awk -F'login=\"' '{print $2}' | awk -F':' '{print $1}'"])
    if stderr:
        logger.exception("error in fetching dbname")
    else:
        dbname = stdout.replace('\n', '').replace('\t', '').replace(' ', '')

    return dbname


def check_mailbox_status():
    """checks the health of mailbox using camp-glops

    Returns:
        integer: 1 if there are issues 0 if none
    """
    counter = 1
    command = "camp-glops -check -v"
    stdout, stderr = run_commands([command])

    if "Mailbox(es) are ok" in stdout:
        logger.info("Mailboxes are healthy")
        counter = 0
    elif "Mailbox(es) are ok" not in stdout:
        logger.info("Mail box isn't healthy, proceed to restart inMail")
    elif stderr:
        logger.info("error in checking mailbox status, exiting..")

    return counter


def restart_inMail():
    """Restart the inmail nlserver

    Returns:
        None
    """
    hostname = get_hostname_new()
    time.sleep(10)
    commands = [
        "nohup /usr/bin/sudo -u neolane bash -c '. /usr/local/neolane/nl*/env.sh ; nlserver restart inMail@" +
        hostname+" -noconsole' > /dev/null &"
    ]
    print(commands)
    try:
        result = subprocess.check_output(
            commands[0], shell=True, universal_newlines=True, timeout=15)
    except subprocess.TimeoutExpired:
        logger.exception("timed out")
        sys.exit(0)
    # THE BELOW STATEMENT IS COMMENTED, I.E., IT WON'T RUN THE RESTART INMAIL COMMAND
    # stdout, stderr = run_commands(commands)
    time.sleep(40)
    return


def install_camp_glops():
    """Install the camp glops if not installed
    """
    commands = [
        "apt-get update -y",
        "apt-get install camp-glops -y",
        "/etc/init.d/camp-glops start",
        "update-rc.d camp-glops enable",
        "camp-glops -check -check-details",
    ]
    stdout, stderr = run_commands(commands)
    logger.info(stdout)
    logger.exception(stderr)


def disable_dovecot():
    commands = [
        "/etc/init.d/dovecot stop",
        "update-rc.d dovecot disable"
    ]
    stdout, stderr = run_commands(commands)
    logger.info(stdout)
    logger.exception(stderr)


def kill_process_dovecot():
    command = [
        "ps -eo pid,command | egrep '/usr/sbin/dovecot' | grep -v grep | awk '{print $1}'"]
    stdout, stderr = run_commands(command)
    if stderr:
        logger.exception("error in getting process id")
        return

    process_id = stdout.strip("\n")

    command = ["kill -9 "+process_id]
    stdout, stderr = run_commands(command)
    if stderr:
        logger.exception("error in killing process id")
        return


def check_for_installation():
    commands = [
        "ps -ef | egrep 'dovecot|glops'"
    ]
    stdout, stderr = run_commands(commands)
    if stderr:
        logger.exception("error in checking processes.. returning")
        return

    if "/usr/sbin/dovecot" in stdout:
        kill_process_dovecot()
        disable_dovecot()
        time.sleep(5)

    if "/usr/bin/camp-glops" in stdout:
        logger.info("camp_glops already installed.. exiting")
        return
    else:
        install_camp_glops()


def change_content_in_files(filename, find_text, replace_text, flag=0):
    with fileinput.FileInput(filename, inplace=True) as f1:
        for line in f1:
            if flag == 1:
                if line.startswith(find_text):
                    print(replace_text, end='\n')
                else:
                    print(line, end='')
            else:
                if find_text in line:
                    print(line.replace(find_text,
                                       replace_text), end='')
                else:
                    print(line, end='')



def fix_inmail_extaccounts():
    hostname = get_hostname_new()
    dbname = get_db_name()
    sql_retrieve_command = "psql -d "+dbname + \
        " -c \"SELECT iextaccountid,saccount,sname,sserver,sport,spassword FROM nmsextaccount WHERE itype = 0 and iactive = 1;\" | awk -F\"|\" 'NR==3 {if($6==\" \") print $1}'"
    logger.info(sql_retrieve_command)
    stdout, stderr = run_commands([sql_retrieve_command])
    print(stderr)
    if 'PGSQL.5432" failed: No such file or directory' in stderr:
        stdout1,stderr1 = run_commands((['eval $(camp-db-params -e)']))
        print('DB Error loop After running fix Out- ',stdout1,' Error - ',stderr1)
    iextaccountid = stdout.strip("\t").strip("\n").strip(" ")
    logger.info(iextaccountid)
    if iextaccountid != "":
        delete_command = "psql -d "+dbname + \
            " -c \"DELETE FROM nmsextaccount WHERE iextaccountid = "+iextaccountid+";\""
        print(delete_command)
        stdout, stderr = run_commands([delete_command])
        logger.exception(stderr)

        filename = "create_extaccount.js"
        data = """xtk.session.Write(
        {
            "extAccount": {
                    "name": "defaultPopAccount",
                    "active": "true",
                    "xtkschema": "nms:extAccount",
                    "account": "neolane",
                    "name": "defaultPopAccount",
                    "password": "",
                    "server": "localhost",
                    "port": "110",
                    "type": 0,
            }
        }
    )
    """
        f = open(filename, "w")
        f.write(data)
        f.close()

        create_command = "/usr/bin/sudo -u neolane bash -c '. /usr/local/neolane/nl*/env.sh ; nlserver javascript -instance:"+hostname+" -file "+filename
        stdout, stderr = run_commands([create_command])
        logger.exception(stderr)

def check_throughput():
    throughput = ""
    #stdout, stderr = run_commands(
    command = ["camp-glops -check -check-details | grep neolane | awk -F\| '{print $5}' | awk '{$1=$1;print}' | awk -F" " '{print $1}'"]
    #stdout = subprocess.check_output(
        #command[0], shell=True, universal_newlines=True, timeout=15)
    process = subprocess.Popen(command, shell=True, universal_newlines=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if stderr:
        logger.exception("error in fetching throughput")
    #else:
    print('throughput ', stdout)
    throughput = stdout.replace('\n', '').replace(
            '\t', '').replace(' ', '')

    try:
        throughput = int(throughput)
    except Exception:
        logger.exception("error in converting throughput into integer")

    return throughput


if __name__ == '__main__':
    try:
        #context.set_logger("inmail")
        global logger
        logger = logging.getLogger('inmail')
    except Exception as e:
        raise e

    check_for_installation()
    time.sleep(10)

    change_content_in_files('/etc/hosts', '::1	        localhost ip6-localhost ip6-loopback',
                            '::1	        ip6-localhost ip6-loopback')
    change_content_in_files(
        '/etc/glops/glops.ini', 'Listen = "[::1]:110,127.0.0.1:110"', 'Listen = "127.0.0.1:110"')

    not_healthy = check_mailbox_status()
    if not_healthy:
        time.sleep(15)
        restart_inMail()

    hostname = get_hostname_new()
    command = ['ls /usr/local/neolane/nl*/conf/config-'+hostname+'.xml']
    stdout, stderr = run_commands(command)
    print(stdout)
    print(stderr)
    print('Before updating inmail config file')

    for file in stdout.split("\n"):
        print(file)
        if hostname in file:
            change_content_in_files(file,
                            '<inMail autoStart="true"',
                            '<inMail autoStart="true" maxMsgPerSession="3000" popMailPeriodSec="5" popQueueSize="200" user="neolane"/>',
                            1)
            print('After updating inmail config file')

    # Now we check the throughput after 90 secs.
    #time.sleep(60)
    #throughput = check_throughput()

    # If inmail is not restarted Fix inmail_ext accounts and restart the service.
    #not_healthy = check_mailbox_status()
    #if not_healthy:
        #fix_inmail_extaccounts()
        #time.sleep(15)
        #restart_inMail()

    # Now we check the throughput periodically until 10 mins.
    #throughput = check_throughput()
    command = ["camp-glops -check -check-details"]
    stdout, stderr = run_commands(command)
    print(stdout)
    time.sleep(60)
    elapsed_time = 60
    while elapsed_time < 600:
        if "Mailbox(es) are ok" in stdout:
            logger.info("Mailboxes are healthy")
            print("Mailboxes are healthy, exiting")
        else:
            stdout, stderr = run_commands(command)
            print(stdout)
            time.sleep(60)
            elapsed_time += 60
    else:
        logger.exception("timeout waiting for throughput to down to 500")
        print("Mail size is too big, mails are processing, Exiting script")