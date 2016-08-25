#-*- coding=GBK -*- 

#++++++++++++++++++++++++++++++++++++++++++++++++
# process watcher
# written by huangjian 2010-06-24
#
# start by: python bmcAppWathc.py <config file>
#++++++++++++++++++++++++++++++++++++++++++++++++

import os
import sys
import thread
import socket
import signal
import time
import threading
import traceback
import ConfigParser
import subprocess

#the global config info
class GlobalConfig():
    def __init__(self):
        self.m_enable=True
        self.m_checkConfigInterval = 3
        self.m_checkProcInterval = 2

#the process config info
class ProcessConfig():
    def __init__(self):
        self.m_procName = ""
        self.m_parameter = ""
        self.m_workPath = ""
        self.m_enable = False
        self.m_runType = "expire"
        self.m_weekDay = []
        self.m_time = []
        
    def equal(self, procConf):
        if self.m_procName != procConf.m_procName:
            return False
        if self.m_parameter != procConf.m_parameter:
            return False
        if self.m_workPath != procConf.m_workPath:
            return False
        if self.m_enable != procConf.m_enable:
            return False
        if self.m_runType != procConf.m_runType:
            return False
        if len(self.m_weekDay) != len(procConf.m_weekDay):
            return False
        for i in xrange(len(self.m_weekDay)):
            if self.m_weekDay[i] != procConf.m_weekDay[i]:
                return False
        if len(self.m_time) != len(procConf.m_time):
            return False
        for i in xrange(len(self.m_time)):
            if self.m_time[i][0] != procConf.m_time[i][0]:
                return False
            if self.m_time[i][1] != procConf.m_time[i][1]:
                return False        
        return True
    
    def __str__(self):
        ret =  "<proc item>" + "\n"
        ret += "    proc_name: " + self.m_procName + "\n"
        ret += "    parameter: " + self.m_parameter + "\n"
        ret += "    work_path: " + self.m_workPath + "\n"
        ret += "    enable: " + str(self.m_enable) + "\n"
        ret += "    run_type: " + str(self.m_runType) + "\n"
        ret += "    week_day: " + str(self.m_weekDay) + "\n"
        ret += "    time: " + str(self.m_time) + "\n"
        ret += "</proc item>"
        return ret
        
#the process info, include config info and runtime info
class ProcessInfo():
    def __init__(self):
        #config info
        self.m_procConf = ProcessConfig()
        
        #runtime info
        self.m_procInfo = None
        
        #startup time
        self.m_startupTime = -1
        

class ProcessWatcher():
    def __init__(self):
        self.m_configFilePath = sys.argv[1]
        self.m_logger = None
        self.m_configParser = None
        self.m_checkConfigTime = 0
        self.m_checkProcTime = 0
        self.m_configFileModifiedTime = 0
        self.m_globalConfig = GlobalConfig()
        self.m_procRuntimeMap = {}
        self.m_procConfigMap = {}
        
        self.doInit()
        
        self.checkConfigFile()
        self.checkProcState()
        
    def doInit(self):
        try:
            self.m_configParser = ConfigParser.ConfigParser()
            self.m_configParser.read(self.m_configFilePath)
            logFilePath = self.m_configParser.get("bmcAppWatch", "log_path")
            logFilePath += "/" + "bmcAppWatch.log"
            self.m_logger = Logger(logFilePath, "a", True)
            self.m_logger.log("")
            self.m_logger.log("++++++++++++++++++++++++++++++++++++++")
            self.m_logger.log("Init successfully, bmcAppWatch started")
            self.m_logger.log("++++++++++++++++++++++++++++++++++++++")
        except:
            print "Init failed, check config file, please"
            sys.exit(0)
        
    def run(self):
        while True:
            nowt = time.time()
            if nowt - self.m_checkConfigTime >= self.m_globalConfig.m_checkConfigInterval:
                self.checkConfigFile()
                self.m_checkConfigTime = time.time()
            if nowt - self.m_checkProcTime >= self.m_globalConfig.m_checkProcInterval:
                self.checkProcState()
                self.m_checkProcTime = time.time()
            try:
                time.sleep(1)
            except:
                pass
        
    def checkConfigFile(self):            
        #check whether the config file modify time is changed
        configFileModifiedTime = int(os.path.getmtime(self.m_configFilePath))
        if configFileModifiedTime == self.m_configFileModifiedTime:
            return
        self.m_configFileModifiedTime = configFileModifiedTime
        self.m_logger.log("")
        self.m_logger.log("Config file was modified, check it")
        
        try:
            self.m_configParser = ConfigParser.ConfigParser()
            self.m_configParser.read(self.m_configFilePath)
            sections = self.m_configParser.sections()
            
            #clear code must be at correct place, take carefullly
            self.m_procConfigMap.clear()
            for section in sections:
                if section == "bmcAppWatch":
                    self.parseGlobalConfig()
                else:
                    self.parseProcConfig(section)
        except:
            self.m_logger.log("Failed to parse config file: %s"%(self.m_configFilePath))
            return
            
        for procItem in self.m_procRuntimeMap.keys():
            if procItem not in self.m_procConfigMap:
                self.m_logger.log("Config item: %s -- removed"%(procItem))
        for procItem in self.m_procConfigMap.keys():
            if procItem not in self.m_procRuntimeMap:
                self.m_logger.log("Config item: %s -- added"%(procItem))
            else:
                if not self.m_procRuntimeMap[procItem].m_procConf.equal(self.m_procConfigMap[procItem]):
                    self.m_logger.log("Config item: %s -- modified"%(procItem))
                else:
                    self.m_logger.log("Config item: %s -- keep same"%(procItem))
                    
        self.m_logger.log("Config file check done")
        self.m_logger.log("")
            
    def parseGlobalConfig(self):
        try:
            self.m_globalConfig.m_enable = not self.m_configParser.get("bmcAppWatch", "enable") == "0"
            self.m_globalConfig.m_checkConfigInterval = int(self.m_configParser.get("bmcAppWatch", "check_conf_interval"))
            self.m_globalConfig.m_checkProcInterval = int(self.m_configParser.get("bmcAppWatch", "check_proc_interval"))
        except:
            self.m_globalConfig.m_enable = True
            self.m_checkConfigInterval = 3
            self.m_checkProcInterval = 2
            self.m_logger.log("Global config invalid, reset to default") 
            
    def parseProcConfig(self, procItem):
        isValid = True
        procConf = ProcessConfig()
        try:
            procConf.m_procName = self.m_configParser.get(procItem, "proc_name")
            procConf.m_parameter = self.m_configParser.get(procItem, "parameter")
            procConf.m_workPath = self.m_configParser.get(procItem, "work_path")
            procConf.m_enable = not self.m_configParser.get(procItem, "enable") == "0"
            procConf.m_runType = self.m_configParser.get(procItem, "run_type")
            weekDay = self.m_configParser.get(procItem, "week_day")
            dayTime = self.m_configParser.get(procItem, "time")
            
            if procConf.m_procName == "":
                isValid = False
            
            if procConf.m_runType not in ("expire", "autoend"):
                isValid = False
               
            #parse week day  
            weekDayRet = self.parseConfigMultiValue(weekDay)
            for item in weekDayRet:
                intValue1 = int(item[0])
                intValue2 = int(item[1])
                if intValue1 >= 1  and intValue2 <=7 and intValue1 <= intValue2:
                    for wday in xrange(intValue1, intValue2 + 1, 1):
                        procConf.m_weekDay.append(wday)
                else:
                    isValid = False
            
            #parse day time
            dayTimeRet = self.parseConfigMultiValue(dayTime)
            for item in dayTimeRet:
                value1 = self.parseConfigTimeValue(item[0])
                value2 = self.parseConfigTimeValue(item[1])
                if value1 == None or value2 == None:
                    isValid = False
                else:
                    if procConf.m_runType == "autoend":
                        #adjust time duration
                        value2 = value1
                    procConf.m_time.append([value1, value2])
        except:
            self.m_logger.log(traceback.format_exc())
            isValid = False
        finally:
            if isValid:
                self.m_procConfigMap[procItem] = procConf
                self.m_logger.log("Load config item: " + procItem)
            else:
                self.m_logger.log("Load config item: " + procItem + " -- invalid")
        
    #parse multi-value in config item
    def parseConfigMultiValue(self, value):
        ret = []
        items = value.split(",")
        for item in items:
            item = item.strip()
            subItems = item.split("-")
            retItem = []
            if len(subItems) > 0:
                subItem = subItems[0].strip()
                retItem = [subItem, subItem]
            if len(subItems) > 1:
                subItem = subItems[1].strip()
                retItem[1] = subItem
            if len(retItem) > 0:
                ret.append(retItem)
        
        return ret
    
    #parse time value in config item
    def parseConfigTimeValue(self, value):
        ret = None
        items = value.split(":")
        if len(items) == 2:
            item1 = int(items[0].strip())
            item2 = int(items[1].strip())
            if (item1 >= 0 and item1 <= 24) and (item2 >=0 and item2 < 60):
                ret = item1 * 100 + item2
        return ret
        
    #check whether the old process expired or not
    def checkProcState(self):
        self.m_logger.log("")
        if self.m_globalConfig.m_enable == False:
            self.m_logger.log("Global config disabled")
            #remove all config items and all processes will be terminated
            self.m_procConfigMap.clear()
        else:
            self.m_logger.log("Global config enabled")
            
        for procItem in self.m_procRuntimeMap.keys():
            #kill old process
            if procItem not in self.m_procConfigMap:
                procInfo = self.m_procRuntimeMap[procItem]
                self.killProcess(procItem)
                if not self.isProcessAlive(procInfo):
                    del self.m_procRuntimeMap[procItem]
                
        for procItem in self.m_procConfigMap.keys():
            #add new process
            if procItem not in self.m_procRuntimeMap:
                if self.isProcessShouldStart(self.m_procConfigMap[procItem]):
                    self.createProcess(procItem)
                else:
                    procInfo = ProcessInfo()
                    procInfo.m_procConf = self.m_procConfigMap[procItem]
                    self.m_procRuntimeMap[procItem] = procInfo
            else:
                procInfo = self.m_procRuntimeMap[procItem]
                procConf = self.m_procConfigMap[procItem]
                if not procInfo.m_procConf.equal(procConf):
                    #config modified, try to kill process firstly
                    self.killProcess(procItem)
                    #update process config info if process is not running
                    if not self.isProcessAlive(procInfo):
                        procInfo.m_procConf = procConf
                        procInfo.m_startupTime = -1
                else:
                    if not procInfo.m_procConf.m_enable:
                        self.m_logger.log("Process disabled: %s"%(procItem))
                        #disabled, try to kill process
                        self.killProcess(procItem)
                    elif not self.isOnWorkingDay(procInfo.m_procConf):
                        self.m_logger.log("Process expired: %s"%(procItem))
                        #expired, try to kill process
                        self.killProcess(procItem)
                    elif not self.isAtWorkingTime(procInfo.m_procConf):
                        if procConf.m_runType == "expire":
                            self.m_logger.log("Process expired: %s"%(procItem))
                            #expired, try to kill process
                            self.killProcess(procItem)
                        elif procConf.m_runType == "autoend":
                            if self.isProcessAlive(procInfo):
                                self.m_logger.log("Process running: %s"%(procItem))
                            else:
                                self.m_logger.log("Process finished: %s"%(procItem))
                    elif not self.isProcessAlive(procInfo):
                        if procConf.m_runType == "expire":
                            self.m_logger.log("Process disappeared: %s"%(procItem))
                            #try to start process
                            self.createProcess(procItem)
                        elif procConf.m_runType == "autoend":
                            nowtime = (int(time.time())) / 60
                            if procInfo.m_startupTime == nowtime:
                                self.m_logger.log("Process finished: %s"%(procItem))
                            else:
                                #try to start process
                                self.createProcess(procItem)
                    else:
                        if procConf.m_runType == "expire":
                            self.m_logger.log("Process running: %s"%(procItem))
                        elif procConf.m_runType == "autoend":
                            nowtime = (int(time.time())) / 60
                            if procInfo.m_startupTime == nowtime:
                                self.m_logger.log("Process running: %s"%(procItem))
                            else:
                                #try to kill process
                                self.killProcess(procItem)
                        
    def createProcess(self, procItem):
        procConf = self.m_procConfigMap[procItem]
        procInfo = ProcessInfo()
        procInfo.m_procConf = procConf
        try:
            self.m_logger.log("Creating process: %s"%(procItem))
            exeargs = [procConf.m_procName]
            for param in procConf.m_parameter.split():
                exeargs.append(param)
            procInfo.m_procInfo = subprocess.Popen(exeargs, cwd = procConf.m_workPath)
            nowtime = (int(time.time())) / 60
            procInfo.m_startupTime = nowtime
        except:
            procInfo.m_procInfo = None
            self.m_logger.log("Failed to create process: %s"%(procItem))
        self.m_procRuntimeMap[procItem] = procInfo
            
    def killProcess(self, procItem):
        procInfo = self.m_procRuntimeMap[procItem]
        if self.isProcessAlive(procInfo):
            self.m_logger.log("Killing process: %s"%(procItem))
            try:
                if sys.platform.lower().find("win") >= 0:
                    #In python2.6, it should use subprocess.Popen.terminate()
                    subprocess.TerminateProcess(int(procInfo.m_procInfo._handle), -9)
                else:
                    #In python2.5, it should use os.kill()
                    procInfo.m_procInfo.kill()
            except:
                self.m_logger.log("Failed to kill process: %s"%(procItem))
            
            
    def isProcessAlive(self, procInfo):
        return procInfo.m_procInfo != None and procInfo.m_procInfo.poll() == None
        
    def isProcessShouldStart(self, procConf):
        return procConf.m_enable and self.isOnWorkingDay(procConf) and self.isAtWorkingTime(procConf)
        
    def isOnWorkingDay(self, procConf):
        tm = time.localtime()
        weekDay = tm.tm_wday + 1
        return weekDay in procConf.m_weekDay
        
    def isAtWorkingTime(self, procConf):
        ret = False
        tm = time.localtime()
        nowtime = tm.tm_hour * 100 + tm.tm_min
        if len(procConf.m_time) == 0:
            ret = True
        for item in procConf.m_time:
            if item[0] <= item[1]:
                if nowtime >= item[0] and nowtime <= item[1]:
                    ret = True
                    break
            else:
                if nowtime >= item[0] or nowtime <= item[1]:
                    ret = True
                    break
        return ret

class Logger():
    def __init__(self, filePath, fileMode, printConsole=False):
        self.m_printConsole = printConsole
        self.m_logFile = file(filePath, fileMode)
        
    def log(self, msg):
        logStr = time.strftime("%Y-%m-%d %X", time.localtime()) + " " + msg
        if self.m_printConsole:
            print logStr
        if self.m_logFile:
            try:
                self.m_logFile.write(logStr)
                self.m_logFile.write("\n")
                self.m_logFile.flush()
            except:
                pass

g_instanceMutexSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
def checkInstanceExist():
    # The method of making single instance is to listen on some port and to check the port exist or not.
    # It's too simple, too naive, but usually work.
    ret = False
    HOST = '127.0.0.1'   #Only listen on local address
    PORT = 65519         #It should be high port number to avoid conflict
    try:
        g_instanceMutexSocket.bind((HOST, PORT))
        g_instanceMutexSocket.listen(1)
    except:
        ret = True
    
    return ret
    
def captureSignal():
    signal.signal(signal.SIGABRT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
                
def showHelp():
    print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
    print "This program is a process watcher that kills or starts a process"
    print "start by: python bmcAppWatch.py <config file>"
    print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
        
def run():
    if (not os.path.exists(sys.argv[1])):
        print 'Wrong config file: %s'%(sys.argv[1])
        sys.exit(0)
    else:
        captureSignal()
        g_watcher = ProcessWatcher()
        g_watcher.run()

if __name__ == "__main__":
    if (len(sys.argv) < 2 or sys.argv[1] == "-h" or sys.argv[1] == "--help"):
        showHelp()
    elif checkInstanceExist() == True:
        print 'The program instance exists, check it.'
    else:
        run()
    