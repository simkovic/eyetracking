import os, datetime, time,sys
try:
    from iViewXAPI import  * #iViewX library
except ImportError:
    print 'Warning: SMI Sdk import Failed'
    
from psychopy.core import Clock
from psychopy import visual, event,core
import numpy as np

def myCm2deg(cm,dist):
    return cm/(dist*0.017455) 
def myDeg2cm(deg,dist):
    return deg*dist*0.017455
def myDeg2pix(deg,dist,cent,width):
    cm = myDeg2cm(deg,dist)
    return myCm2pix(cm,cent,width)

# here are some constants, settings and helper functions
class ETSTATUS():
    OFF, FOUND, CREATED, SETUPFINISHED,CALSTARTED, CALFAILED,CALSUCCEEDED, CALRECEIVED, CALACCEPTED, TRACKING=range(10)
    toString = ('Not Found', 'Found', 'Connected', 'Finished Setup','Started Calibration',
        'Calibration Failed','Calibration was Successful', 'Received Calibration Data', 
        'Calibration Accepted', 'Tracking Finished')

class Settings():
    """ I put here everything I considered worth varying"""
    # fixation extraction
    THETA=0.9; # parameter for online exponential smoothing AR(1) filter
    FIXVTH=40 # upper velocity threshold for fixations in deg per sec
    FIXMINDUR=0.06 # minimum fixation duration in seconds
    FUSS=10 # sample size over which the average fixation target position is computed
    BLINKTOL=30 # minimum nr of consecutive blink data required to interupt a fixation
    POLLINGDUR=1 # seconds, max wait time for fixation in getFixation
    MAXDEV=3 # deg, maximum allowed deviance at trial start
    clock=Clock()

class TrackerSMI:
    
    def __init__(self, win,sj=0,block=0,verbose=False,target=None):
        """ Initialize controller window, connect and activate eyetracker
            win - supply a window where the experiment is shown
            sid - subject id
            block - block nr, for experiments with several blocks
        """
        self.etstatus=ETSTATUS.OFF
        self.sid=sj
        self.block=block
        self.verbose=verbose
        self.target=target
        self.eyetracker = None
        self.win = win # this window is where the experiment is displayed to subject
        self.sd=sampleData
        # lets start, initialize, find and activate the eyetracker
        res = iViewXAPI.iV_Connect(c_char_p('147.142.240.109'), c_int(4444),c_char_p('147.142.240.108'), c_int(5555))
        if res!=1: print 'Connection failed with code ', res
        else: self.etstatus=ETSTATUS.CREATED
        redSetup1=CStandAlone(410,312,955,750,120,35)# stimx,stimy,floor2screen, floor2red, screen2red,angle
        redSetup2=CStandAlone(410,312,955,885,120,15)
        #res = iViewXAPI.iV_SetupREDStandAloneMode(byref(redSetup1))
        print "iV_SetupStandAloneMode " + str(res)
        iViewXAPI.iV_GetSystemInfo(byref(systemData))
        self.hz=float(systemData.samplerate)
        self.fname='VP%03dB%d'%(self.sid,self.block)
        # main menu vars
        self.msg=visual.TextStim(self.win,height=0.05,units='norm',
                color='white', text='')
        # fixation extraction
        self.fixBlinkCount=0
        self.fixloc=np.array((np.nan,np.nan))
        self.fixsum=np.array((np.nan,np.nan))
        self.fixdur=0
        
        self.doMain()
        
        

        
    def getStatus(self):
        return self.etstatus
    def destroy(self):
        iViewXAPI.iV_Disconnect()
        
        
    ############################################################################
    # mainscreen methods
    ############################################################################
    def doMain(self):
        if not self.etstatus>=ETSTATUS.CREATED:
            print 'doMain >> eyetracker not connected'
            return False
        
        self.msg.setText('Welcome to SMI\n\tEyetracker Status: %s\n' %ETSTATUS.toString[self.etstatus]
            +'Press:\n\tS - show setup screen \n\tC - calibrate \n\tE - run Experiment \n\tESC - Abort')
        while True: # stay within the main section until experiment starts
            self.msg.draw()
            self.win.flip()
            for key in event.getKeys():
                if 's' == key: self.doSetup()
                elif 'c' == key: 
                    self.doCalibration()
                    if self.etstatus==ETSTATUS.CALACCEPTED:
                        acc='Accuracy:\n\tLX= %.3f, RX= %.3f\n\tLY= %.3f, RY= %.3f\n'%self.accInfo
                    else: acc=''
                    self.msg.setText('Welcome to SMI\n\tEyetracker Status: '+
                        '%s\n' %ETSTATUS.toString[self.etstatus]+acc+'Press:\n\tS - show'+
                        ' setup screen \n\tC - calibrate \n\tE - run Experiment \n\tESC - Abort')
                elif 'e' == key:
                    res=iViewXAPI.iV_StartRecording()
                    print "iV_StartRecording " + str(res)
                    acc='Accuracy: LX= %.3f, RX= %.3f LY= %.3f, RY= %.3f'%self.accInfo
                    self.sendMessage(acc)
                    #res=iViewXAPI.iV_PauseRecording()
                    #print "iV_PauseRecording " + str(res)
                    return # start experiment
                elif 'escape' == key: # abort
                    self.closeConnection()
                    self.win.close()
                    sys.exit()
                else: 'TODO'
            time.sleep(0.01)
        
        
        
            
    ############################################################################
    # setup methods
    ############################################################################
    def doSetup(self):
        ''' setup '''
        res=iViewXAPI.iV_ShowTrackingMonitor()
        print "iV_ShowTrackingMonitor " + str(res)

        
        
    ############################################################################
    # calibration methods
    ############################################################################
    
    def doCalibration(self, paced=True,calibrationGrid=np.ones((3,3)),
        stimulus=None,soundStim=None, shrinkingSpeed=1.5, rotationSpeed=-2):
        calibrationData = CCalibration(9, 1, 0, 0, 1, 255, 128, 3, 15, b"")

        res = iViewXAPI.iV_SetupCalibration(byref(calibrationData))
        print "iV_SetupCalibration " + str(res)
        res = iViewXAPI.iV_Calibrate()
        print "iV_Calibrate " + str(res)

        res = iViewXAPI.iV_Validate()
        print "iV_Validate " + str(res)

        res = iViewXAPI.iV_GetAccuracy(byref(accuracyData), 0)
        print "iV_GetAccuracy " + str(res)
        self.accInfo=(accuracyData.deviationXLeft,accuracyData.deviationXRight,accuracyData.deviationYLeft,accuracyData.deviationYRight )
        print "deviationXLeft " + str(accuracyData.deviationXLeft) + " deviationYLeft " + str(accuracyData.deviationYLeft)
        print "deviationXRight " + str(accuracyData.deviationXRight) + " deviationYRight " + str(accuracyData.deviationYRight)
        self.etstatus=ETSTATUS.CALACCEPTED
        
    ############################################################################
    # tracking methods
    ############################################################################
    


    
    def closeConnection(self):
        res=iViewXAPI.iV_StopRecording()
        print "iV_StopRecording " + str(res)
        res=iViewXAPI.iV_SaveData(str(self.fname),str(''), str(self.sid),1)
        print "iV_SaveData " + str(res)
        iViewXAPI.iV_Disconnect()

    def sendMessage(self, msg):
        '''Record a message to the tracker'''
        #print(msg)
        iViewXAPI.iV_SendImageMessage(c_char_p(msg))
        #self.tracker.sendMessage(msg)
        
    def preTrial(self, trial, calibTrial, win,autoDrift=False):
        '''Set up each trial with the eye tracker
        '''
        
        #? paralel with getSample ?
        #res=iViewXAPI.iV_ContinueRecording(c_char_p("TRIALID %s"%trial))
        #print "iV_ContinueRecording " + str(res)
        self.sendMessage("TRIALID %s"%trial)
        
 
        #determine which eye(s) are available
        if autoDrift:
            self.target.setPos((0, 0))
            self.target.draw()
            win.flip()

            i=0
            core.wait(0.5)
            while i<10:
                fc=self.getFixation(units='deg')
                if fc!=None: #success
                    dist=(fc[0]**2+fc[1]**2)**0.5
                    if dist< Settings.MAXDEV:
                        cmd='drift %f %f ' % (fc[0],fc[1])
                        #if sample.getEye()==1:rightFinished=True; cmd+=' R'
                        #else: leftFinished=True; cmd+=' L'
                        self.sendMessage(cmd)
                        break
                    else:
                        core.wait(0.1)
                i+=1
                #print i,fc
            if i==10:
                self.postTrial()
                self.doMain()
                self.preTrial(trial, calibTrial, win,autoDrift)
            else: core.wait(0.25+np.random.random()/2.0)
 
 
 
    def postTrial(self):
        '''Ends recording: adds 100 msec of data to catch final events'''
        self.sendMessage("POSTTRIAL")
        core.wait(0.1)
        #res=iViewXAPI.iV_PauseRecording()
        #print "iV_PauseRecording " + str(res)
        
        
    def getGazePosition(self,eyes=1,units='norm'):
        ''' returns the gaze postion of the data
            returns None if there are no new data
            if coordinates are invalid, returns nan values
            eyes - 1: average coordinates of both eye are return as ndarray with 2 elements
                    2: coordinates of both eyes are returned as ndarray with 4 elements
            units - units of output coordinates
                    'norm', 'pix', 'cm' and 'deg' are currently supported
        '''
        if units is 'norm': xscale=2; yscale=2
        elif units is 'pix': 
            xscale=self.win.size[0]; yscale=self.win.size[1]
        elif units is 'cm':
            xscale=self.win.monitor.getWidth(); 
            yscale=self.win.size[1]/float(self.win.size[0])*self.win.monitor.getWidth()
        elif units is 'deg':
            xscale=self.win.monitor.getWidth(); 
            yscale=self.win.size[1]/float(self.win.size[0])*self.win.monitor.getWidth()
            xscale=myCm2deg(xscale, self.win.monitor.getDistance())
            yscale=myCm2deg(yscale, self.win.monitor.getDistance())
        else: raise ValueError( 'Wrong or unsupported units argument in getGazePosition')

        res=iViewXAPI.iV_GetSample(byref(self.sd))
        g=self.sd
        if res==2: return None # no new data available
        elif res!=1 or (g.leftEye.gazeX==0 and g.leftEye.gazeY==0):
            #print 'iV_GetSample ',res,g.leftEye.gazeX,g.leftEye.gazeY
            return np.ones( eyes*2)*np.nan
        
        out= [g.leftEye.gazeX/float(self.win.size[0])*xscale-xscale/2.0, 
                -g.leftEye.gazeY/float(self.win.size[1])*yscale+yscale/2.0,
                g.rightEye.gazeX/float(self.win.size[0])*xscale-xscale/2.0, 
                -g.leftEye.gazeY/float(self.win.size[1])*yscale+yscale/2.0]
        #print g.leftEye.gazeX, g.leftEye.gazeY, out[0],out[1]
        if eyes==2: return np.array(out)
        avg=[(out[0]+out[2])/2.0, (out[1]+out[3])/2.0]
        return np.array(avg)

    def computeFixation(self,cgp):
        if cgp == None: return # no new data
        if np.isnan(cgp[0]): # handle blinks
            self.fixBlinkCount+=1
            if self.fixBlinkCount>=Settings.BLINKTOL: # interupt any ongoing fixation
                self.fixloc=np.array([np.nan,np.nan]); self.fixdur=0
                self.fixsum=np.array([np.nan,np.nan]);
            return
        else: self.fixBlinkCount=0
        if not np.isnan(self.fixloc[-1]):
            fixlocold=np.copy(self.fixloc)
            # do exponential smoothing on the data
            self.fixloc= Settings.THETA*self.fixloc+(1-Settings.THETA)*cgp
            if self.fixdur < Settings.FUSS: self.fixsum+=cgp # take fixation target as its center
            velocity=self.fixloc-fixlocold;
            #self.vel.append(np.linalg.norm(velocity)*self.hz)
            isSac= np.linalg.norm(velocity)*self.hz> Settings.FIXVTH
            if not isSac: self.fixdur+=1; return
        self.fixloc=np.copy(cgp)
        self.fixsum=np.copy(cgp)
        self.fixdur=1

    def getCurrentFixation(self, units='deg'):
        ''' returns the triple gc,fc,fix
            where gc is current gaze position, fc is current fixation position (or nans if not available)
            and fix indicates whether a fixation is currently taking place
            units - units of output coordinates
                    'norm', 'pix', 'cm' and 'deg' are currently supported
        '''
        cgp=self.getGazePosition(eyes=1,units='deg')
        self.g=cgp
        self.computeFixation(cgp)
        fd=self.fixdur/self.hz
        fc=self.fixsum/float(Settings.FUSS)#/float(max(self.fixdur,1))
        if units is 'cm': fc=deg2cm(fc, self.win.monitor)
        elif units is 'pix': fc=deg2pix(fc, self.win.monitor)
        elif units is 'norm': fc = deg2pix(fc, self.win.monitor) / self.win.size*2
        return fc, fd>Settings.FIXMINDUR
        
        

    def getFixation(self,units='deg'):
        self.fixBlinkCount=0
        self.fixloc=np.array((np.nan,np.nan))
        self.fixsum=np.array((np.nan,np.nan))
        self.vel=[]
        self.fixdur=0
        t0=Settings.clock.getTime()
        self.d=[]
        while (Settings.clock.getTime()-t0<Settings.POLLINGDUR):
            fc, isFix=self.getCurrentFixation(units=units)
##            if self.g == None:
##                self.d.append([fc[0],fc[1],isFix,self.fixdur,self.fixloc[0],
##                           self.fixloc[1],-99,-99])
##            else:
##                self.d.append([fc[0],fc[1],isFix,self.fixdur,self.fixloc[0],
##                           self.fixloc[1],self.g[0],self.g[1]])
            if isFix: return fc # success
            core.wait(0.001)
        return None

        
        
        

if __name__ == "__main__":
    """Run simple gaze contingent demonstration.
    """
    win = visual.Window(size = (900,700), fullscr=True, allowGUI=False, 
                        color=[0,0,0], units='deg', waitBlanking=True,
                        winType = 'pyglet', monitor='smiDell',colorSpace='rgb')
    point = visual.Circle(win,radius=3,units='deg',lineColor='red')
    point2 = visual.Circle(win,radius=3,units='deg',lineColor='green')
    target = visual.PatchStim(win, tex = None, mask = None, 
                              units = 'pix', pos = (0,0), size = (10, 10),  color = [1,1,1])
    note = visual.TextStim(win, pos=[0,0], units = 'pix', text='none', color=(1,1,1))
    clock = core.Clock()
    eyeTracker = TrackerSMI(win,target=point)
    status = eyeTracker.getStatus()
    tr=0
    for Ttype in [True,True,True,True,True]: #loop for each "trial"
        if Ttype: note.setText("Drift Correct Trial")
        else: note.setText("Standard Trial")
        note.draw()
        win.flip()
        core.wait(1)
        eyeTracker.preTrial(tr, Ttype, win,autoDrift=Ttype)
        note.setText("Trial on")
        note.draw()
        win.flip()
        core.wait(2)
        
        eyeTracker.postTrial()
        win.flip()
        #gc.enable()
        tr+=1
    #np.save('D.npy',D)
    win.close()
    eyeTracker.closeConnection()
    print("Self-test completed")
    #core.quit()
