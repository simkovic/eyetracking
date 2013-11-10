# author: Matus Simkovic
# took this from https://github.com/JasonLocklin/psychopy/blob/master/psychopy/hardware/eyeTracker.py
# and adjusted to my needs

import pylink
import sys, os, gc, array, Image, copy,random
from psychopy import visual, info, misc, monitors, event, core
import numpy as np

 
RIGHT_EYE = 1
LEFT_EYE = 0
BINOCULAR = 2
HIGH = 1
LOW = 0
WHITE = (255,255,255)
GRAY = GREY = (128,128,128)
BLACK = (0,0,0)
buttons =(0, 0);
spath = os.path.dirname(sys.argv[0])
if len(spath) !=0: os.chdir(spath)
 
 
 
class EyeLinkCoreGraphicsPsychopy(pylink.EyeLinkCustomDisplay):
    def __init__(self, tracker, display, displaySize):
        '''Initialize a Custom EyeLinkCoreGraphics for Psychopy
        tracker: the TRACKER() object
        display: the Psychopy display window
        '''
        pylink.EyeLinkCustomDisplay.__init__(self)
        self.display = display
        self.displaySize = displaySize
        self.size = (0,0)
        #self.pal = None 
        self.setTracker(tracker)
        self.mouse = event.Mouse(visible=False)
        
        self.text= visual.TextStim(self.display)
        self.imtitle = visual.TextStim(self.display, text = ' ', pos=(0,-10), units='cm')
        #pupil crosshair
        self.pxhair=visual.Line(self.display,units='pix',lineWidth=2)
        self.pyhair=visual.Line(self.display,units='pix',lineWidth=2)
        # pupil box
        self.pupilBox=visual.Rect(self.display,lineColor=(1,0,0),units='pix',lineWidth=2)
        # head crosshair
        self.headHair=[] 
        for i in range(4):
            self.headHair.append((visual.ShapeStim(self.display,units='pix',lineWidth=2),
                visual.ShapeStim(self.display,units='pix',lineWidth=2)))
        self.chair=[] 
        for i in range(4):
            self.chair.append(visual.Line(self.display,units='pix',lineWidth=2))
        self.keys=[]; self.calStart=True
        
        print("Finished initializing custom graphics")
        
    
    def setTracker(self, tracker):
        self.tracker = tracker
        self.tracker_version = tracker.getTrackerVersion()
        print self.tracker_version
        if(self.tracker_version >=3):
            self.tracker.sendCommand("enable_search_limits=YES")
            self.tracker.sendCommand("track_search_limits=YES")
            self.tracker.sendCommand("autothreshold_click=YES")
            self.tracker.sendCommand("autothreshold_repeat=YES")
            self.tracker.sendCommand("enable_camera_position_detect=YES")

    def setup_cal_display(self):
        '''This function is called just before entering calibration or validation modes'''
        self.text.setText('Welcome to Camera Setup\nPress Return to display Cameras'
            +'\nPress C to calibrate\nPress V to validate\nPress O to start experiment')
        if self.tracker.doSetup: self.text.draw()
        self.display.flip()
        print 'setup_cal_display'
    def exit_cal_display(self):
        '''This function is called just before exiting calibration/validation mode'''
        self.display.flip()
        #print 'exit_cal_display'
    def record_abort_hide(self):
        '''This function is called if aborted'''
        pass
    def clear_cal_display(self):
        '''Clear the calibration display'''
        self.display.flip()
        #print 'clear_cal_display'
    def erase_cal_target(self):
        '''Erase the calibration or validation target drawn by previous call to draw_cal_target()'''
        self.display.flip()
        #print 'erase_cal_target'
    def draw_cal_target(self, x, y):
        '''Draw calibration/validation target'''
        if self.calStart:
            calStart=False
            #self.keys=[pylink.KeyInput(ord(' '))]
        self.tracker.target.setPos((x - 0.5*self.displaySize[0], 0.5*self.displaySize[1] - y))
        self.tracker.target.draw()
        self.display.flip()
        #self.tracker.sendCommand("enable_automatic_calibration=YES")
        #print 'draw_cal_target'
    def play_beep(self, beepid):
        ''' Play a sound during calibration/drift correct.'''
        pass

 
    def get_mouse_state(self):
        '''Get the current mouse position and status'''
        pos = self.mouse.getPos()
        state = self.mouse.getPressed()[0]
        print 'h'
    def get_input_key(self):
        '''Check the event buffer for special keypresses'''
        keys= event.getKeys()
        if len(keys)>0: print 'key: ',keys
        ky=copy.copy(self.keys)
        self.keys=[]
        
        for keycode in keys:
            k=-1
            if keycode == 'f1':  k = pylink.F1_KEY
            elif keycode ==  'f2':  k = pylink.F2_KEY
            elif keycode ==   'f3':  k = pylink.F3_KEY
            elif keycode ==   'f4':  k = pylink.F4_KEY
            elif keycode ==   'f5':  k = pylink.F5_KEY
            elif keycode ==   'f6':  k = pylink.F6_KEY
            elif keycode ==   'f7':  k = pylink.F7_KEY
            elif keycode ==   'f8':  k = pylink.F8_KEY
            elif keycode ==   'f9':  k = pylink.F9_KEY
            elif keycode ==   'f10': k = pylink.F10_KEY

            elif keycode ==   'pageup': k = pylink.PAGE_UP
            elif keycode ==   'pagedown':  k = pylink.PAGE_DOWN
            elif keycode ==   'up':    k = pylink.CURS_UP
            elif keycode ==   'down':  k = pylink.CURS_DOWN
            elif keycode ==   'left':  k = pylink.CURS_LEFT
            elif keycode ==   'right': k = pylink.CURS_RIGHT

            elif keycode ==   'backspace':    k = ord('\b')
            elif keycode ==   'return':  k = pylink.ENTER_KEY
            elif keycode ==   'space':  k = ord(' ')
            elif keycode ==   'escape':  k = pylink.ESC_KEY
            elif keycode ==   'tab':     k = ord('\t')
            if k==-1: 
                try: 
                    k=ord(keycode)
                    print keycode
                except TypeError: k=pylink.JUNK_KEY
            ky.append(pylink.KeyInput(k))
        
        return ky
 
    
    def alert_printf(self,msg):
        '''Print error messages.'''
        print "alert_printf"
    def get_search_box(self):
        self.tracker.readRequest("search_limits_drawbox")
        t = pylink.currentTime()
        while(pylink.currentTime()-t < 500):
          rv= self.tracker.readReply()
          if(rv != None and len(rv)>0):
              v =rv.split(' ')
              v[0] = float(v[0])
              v[1] = float(v[1])
              v[2] = float(v[2])
              v[3] = float(v[3])
              return v
    def setup_image_display(self, width, height):
        self.size = (width,height)
        self.clear_cal_display()
        self.imtitle.setAutoDraw(True)
        
    def exit_image_display(self):
        '''Called to end camera display'''
        self.imtitle.setAutoDraw(False)
        self.display.flip()
        
    def image_title(self, text):
        '''Draw title text at the top of the screen for camera setup'''
        
        print text
        self.imtitle.setText(text)
        #self.ititle.draw()
        #self.display.flip()
        
    def draw_cross_hair_eyelinkCL(self):
        """ TODO """
        pass

    def draw_cross_hair_eyelinkII(self):
        xdata = self.tracker.getImageCrossHairData()
        if xdata is None:
            return
        
        w = self.size[0]*3; h = self.size[1]*3
        l =0-w/2.0
        t =0-h/2.0
        wmax = w/6; wmin = wmax/3
        thick = 1 + (w/300)
        col = (255,255,255,255)
        channel = xdata[0]
        x = xdata[1]
        y = xdata[2]
        for i in range(4):#resize to rendered size
            if(x[i] != 0x8000):
                x[i] = (w*x[i])/8192-w/2.0
                y[i] = -(h*y[i])/8192+h/2.0
        
        if(channel == 2):                 # head camera channel: draw marker xhairs 
            for i in range(4):
                if(x[i] != 0x8000):
                    self.headHair[i][0].setVertices(((x[i]-wmax,y[i]),(x[i]+wmax,y[i]) ))
                    self.headHair[i][1].setVertices(((x[i],y[i]-wmax),(x[i],y[i]+wmax)))
                    self.headHair[i][0].draw()
                    self.headHair[i][1].draw()
        else:
            if(x[0] != 0x8000):     # pupil (full-size) xhair
                self.pxhair.setStart((l,y[0])); self.pxhair.setEnd((l+w, y[0]))
                self.pyhair.setStart( (x[0],t)); self.pyhair.setEnd((x[0],t+h))
                self.pxhair.draw()
                self.pyhair.draw()
                
            if(x[1] != 0x8000):     # CR (open) xhair
                self.chair[0].setStart((x[1]-wmax,y[1])); self.chair[0].setEnd((x[1]-wmin, y[1]))
                self.chair[1].setStart((x[1]+wmin,y[1])); self.chair[1].setEnd((x[1]+wmax, y[1]))
                self.chair[2].setStart( (x[1],y[1]-wmax)); self.chair[2].setEnd((x[1],y[1]-wmin))
                self.chair[3].setStart( (x[1],y[1]+wmin)); self.chair[3].setEnd((x[1],y[1]+wmax))
                for i in range(4):
                    self.chair[i].draw()
                    
            if(x[2] != 0x8000):     # pupil limits box
                self.pupilBox.setPos(((x[2]+x[3])/2.0,(y[2]+y[3])/2.0))
                self.pupilBox.setHeight(abs(y[2]-y[3]))
                self.pupilBox.setWidth(abs(x[2]-x[3]))
                self.pupilBox.draw()
                'todo'
    
    def draw_image_line(self, width, line, totlines,buff):		
        #print "draw_image_line",line, len(buff)
        i =0
        while i <width:
            self.imagebuffer.append(self.pal[buff[i]])
            i= i+1
                
        if line == totlines:
            imgsz = (self.size[0]*3,self.size[1]*3)
            bufferv = self.imagebuffer.tostring()
            img =Image.new("RGBX",self.size)
            img.fromstring(bufferv)
            img = img.resize(imgsz)
            self.img= visual.SimpleImageStim(self.display,image=img)
            self.img.draw()
            if(self.tracker_version >=3):
                self.draw_cross_hair_eyelinkCL()
            else:
                self.draw_cross_hair_eyelinkII()
            self.display.flip()
            self.imagebuffer = array.array('l')
            
            
    def set_image_palette(self, r,g,b): 
        '''Given a set of RGB colors, create a list of 24bit numbers representing the pallet.
        I.e., RGB of (1,64,127) would be saved as 82047, or the number 00000001 01000000 011111111'''
        self.imagebuffer = array.array('l')
        self.clear_cal_display()
        sz = len(r)
        i =0
        self.pal = []
        while i < sz:
            rf = int(b[i])
            gf = int(g[i])
            bf = int(r[i])
            self.pal.append((rf<<16) |  (gf<<8) | (bf)) 
            i = i+1        

class TrackerEyeLink():
    def __init__(self, win, clock, sj =0,block=1,doSetup=True, autoCalibration=True, saccadeSensitivity = HIGH, 
        calibrationType = 'HV9', calibrationTargetColor = WHITE,calibrationBgColor = BLACK, 
        CalibrationSounds = False,target=None ):
        '''
        win: psychopy visual window used for the experiment
        clock: psychopy time clock recording time for whole experiment
        sj: Subject identifier string (affects EDF filename)
        autoCalibration:
         True: enable auto-pacing during calibration
 
        calibrationTargetColor and calibrationBgColor:
             RGB tuple, i.e., (255,0,0) for Red
             One of: BLACK, WHITE, GRAY
        calibrationSounds:
         True: enable feedback sounds when calibrating 
        '''
        self.edfFileName = 'vp%03db%d.EDF' % (sj,block)
        print(self.edfFileName)
        inf = info.RunTimeInfo("J","1",win, refreshTest=None, 
                             userProcsDetailed=False)
        self.screenSize = inf['windowSize_pix']
        self.units = inf['windowUnits']
        self.monitorName = inf['windowMonitor.name']
        monitor = monitors.Monitor(self.monitorName)
        
        print("Connecting to eyetracker.")
        self.tracker = pylink.EyeLink()
        if target==None:
            self.tracker.target = visual.PatchStim(win, tex = None, mask = 'circle',
                units='pix', pos=(0,0),size=(6,6), color = [1,1,1] )
        else: self.tracker.target=target
        self.tracker.doSetup=doSetup
        self.timeCorrection = clock.getTime() - self.tracker.trackerTime()
        print("Loading custom graphics")

        genv = EyeLinkCoreGraphicsPsychopy(self.tracker, win, self.screenSize)
        self.tracker.openDataFile(self.edfFileName)
        pylink.flushGetkeyQueue();
        self.tracker.setOfflineMode();
        self.tracker.sendCommand("screen_pixel_coords =  0 0 %d %d"
                                    %( tuple(self.screenSize) ))
        self.tracker.setCalibrationType(calibrationType)
        self.tracker.sendMessage("DISPLAY_COORDS  0 0 %d %d"
                                    %( tuple(self.screenSize) ))
 
        eyelink_ver = self.tracker.getTrackerVersion()
        if eyelink_ver == 3:
            tvstr = self.tracker.getTrackerVersionString()
            vindex = tvstr.find("EYELINK CL")
            tracker_software_ver = int(float(tvstr[(vindex + len("EYELINK CL")):].strip()))
        else: tracker_software_ver = 0
        if eyelink_ver>=2:
            self.tracker.sendCommand("select_parser_configuration %d" %saccadeSensitivity)
        else:
            if saccadeSensitivity == HIGH:
                svt, sat = 22, 5000
            else: svt, sat = 30, 9500
            self.tracker.sendCommand("saccade_velocity_threshold = %d" %svt)
            self.tracker.sendCommand("saccade_acceleration_threshold = %d" %sat)
 
        if eyelink_ver == 2: #turn off scenelink camera stuff
            self.tracker.sendCommand("scene_camera_gazemap = NO")
 
        # set EDF file contents
        #self.tracker.sendCommand("file_event_filter = LEFT,RIGHT,FIXATION,SACCADE,BLINK,MESSAGE,BUTTON,FIXUPDATE")
        self.tracker.sendCommand("file_event_filter = LEFT,RIGHT,BLINK,MESSAGE,BUTTON")
        if tracker_software_ver>=4:
            self.tracker.sendCommand("file_sample_data  = LEFT,RIGHT,GAZE,AREA,GAZERES,STATUS,HTARGET")
        else:
            self.tracker.sendCommand("file_sample_data  = LEFT,RIGHT,GAZE,AREA,GAZERES,STATUS")
        # set link data (used for gaze cursor)
        self.tracker.sendCommand("link_event_filter = LEFT,RIGHT,FIXATION,SACCADE,BLINK,BUTTON,FIXUPDATE")
        self.tracker.sendCommand("fixation_update_interval = 50")
        self.tracker.sendCommand("fixation_update_accumulate = 50")
        if tracker_software_ver>=4:
            self.tracker.sendCommand("link_sample_data  = LEFT,RIGHT,GAZE,GAZERES,AREA,STATUS,HTARGET")
        else:
            self.tracker.sendCommand("link_sample_data  = LEFT,RIGHT,GAZE,GAZERES,AREA,STATUS")
 
        #Set the calibration settings:
        pylink.setCalibrationColors( calibrationTargetColor, calibrationBgColor)
        if CalibrationSounds:
            pylink.setCalibrationSounds("", "", "")
            pylink.setDriftCorrectSounds("", "off", "off")
        else:
            pylink.setCalibrationSounds("off", "off", "off")
            pylink.setDriftCorrectSounds("off", "off", "off")
        
        if autoCalibration:
            self.tracker.enableAutoCalibration()
        else: self.tracker.disableAutoCalibration()
        win.flip()
        print("Opening graphics")
        pylink.openGraphicsEx(genv)
        if doSetup:
            print("Begining tracker setup")
            self.tracker.doTrackerSetup()
        win.flip()
 
    def setTarget(self,target):
        self.tracker.target=target
        
 
    def sendMessage(self, msg):
        '''Record a message to the tracker'''
        print(msg)
        self.tracker.sendMessage(msg)
 
    def sendCommand(self, msg):
        '''Send command to the tracker'''
        self.sendMessage('COMMAND '+msg)
        self.tracker.sendCommand(msg)
 
    def resetEventQue(self):
        '''Reset the eyetracker event cue
            usage: use this prior to a loop calling recordFixation() so
            that old fixations or other events are cleared from the 
            buffer.
        '''
        self.tracker.resetData()
 
 
    def getStatus(self):
        """Return the status of the connection to the eye tracker"""
        if self.tracker.breakPressed():
            return("ABORT_EXPT")
        if self.tracker.escapePressed():
            return("SKIP_TRIAL")
        if self.tracker.isRecording()==0:
            return("RECORDING")
        if self.tracker.isConnected():
            return("ONLINE")
        else:
            return("OFFLINE")
        return("UNKNOWN STATUS: " + str(self.tracker.getStatus()) )
 
    #================================================================
 
 
 
 
 
    #####################################################################
    #    Eyetracker set up and take-down
    #####################################################################
 
    def preTrial(self, trial, calibTrial, win,autoDrift=False):
        '''Set up each trial with the eye tracker
        '''
        self.tracker.doSetup=False
        if calibTrial: cond = "Test/Calibration Trial"
        else: cond = "Non-test/no calibration trial"
        message ="record_status_message 'Trial %d %s'"%(trial+1, cond)
        self.tracker.sendCommand(message)
        msg = "TRIALID %s"%trial
        self.tracker.sendMessage(msg)
        #Do drift correction if necissary
        if calibTrial:
            win.flip()
            while True:
                try:
                    error = self.tracker.doDriftCorrect(self.screenSize[0]/2,self.screenSize[1]/2,1,1) 
                    if error != 27:
                        self.tracker.applyDriftCorrect()
                        break
                    else:
                        
                        #self.tracker.doTrackerSetup()
                        win.flip()
                except:
                    print("Exception")
                    break
            win.flip()

        print("Switching to record mode")
        error = self.tracker.startRecording(1,1,1,1)
        pylink.beginRealTimeMode(100)
        if error: return error
 
        if not self.tracker.waitForBlockStart(1000, 1, 0):
            endTrial()
            print "ERROR: No link samples received!"
            return "ABORT_EXPT"
        self.eye_used = self.tracker.eyeAvailable(); 
        #determine which eye(s) are available
        if self.eye_used == RIGHT_EYE:
            self.tracker.sendMessage("PRETRIAL EYE_USED 1 RIGHT")
        elif self.eye_used == LEFT_EYE :
            self.tracker.sendMessage("PRETRIAL EYE_USED 0 LEFT")
        elif self.eye_used == BINOCULAR:
            self.tracker.sendMessage("PRETRIAL EYE_USED 2 BINOCULAR")
        else:
            print "Error in getting the eye information!"
            return "ABORT_EXPT"
        self.tracker.flushKeybuttons(0)
        if autoDrift:
            self.tracker.target.setPos((0, 0))
            self.tracker.target.draw()
            win.flip()
            
            
            x,y=self.screenSize/2.0
            i=0
            leftFinished=False
            rightFinished=False
            core.wait(0.5)
            self.tracker.resetData()
            while i<10 and not (leftFinished and rightFinished):   
                sampleType = self.tracker.getNextData()
                if sampleType == pylink.FIXUPDATE:
                    sample = self.tracker.getFloatData()
                    gazePos=sample.getAverageGaze()
                    #self.sendMessage('eyePos %.3f %.3f type %d, eye %d'%(gazePos[0],gazePos[1],sample.getType(),sample.getEye()))
                    if (( (x-gazePos[0])**2+(y-gazePos[1])**2)**0.5<misc.deg2pix(3,win.monitor) and
                        gazePos[0]>0 and gazePos[0]<2*x and gazePos[1]>0 and gazePos[1]<2*y):
                        cmd='drift_correction %f %f %f %f' % (x-gazePos[0], y-gazePos[1],x,y)
                        if sample.getEye()==1: rightFinished=True; cmd+=' R'
                        else: leftFinished=True; cmd+=' L'
                        self.sendCommand(cmd)
                    else:
                        core.wait(0.1)
                        self.tracker.resetData()
                        i+=1
            if i==10:
                self.postTrial()
                self.tracker.doTrackerSetup()
                self.preTrial(trial, calibTrial, win,autoDrift)
            else: core.wait(0.25+random.random()/2)
            return
 
 
 
    def postTrial(self):
        '''Ends recording: adds 100 msec of data to catch final events'''
        self.tracker.sendMessage("POSTTRIAL")
        pylink.endRealTimeMode()
        pylink.pumpDelay(100)
        self.tracker.stopRecording()
        while self.tracker.getkey() :
            pass;
 
 
    def closeConnection(self):
        '''Clean everything up, save data and close connection to tracker'''
        if self.tracker != None:
            # File transfer and cleanup!
            self.tracker.setOfflineMode();
            core.wait(0.5)
            #Close the file and transfer it to Display PC
            self.tracker.closeDataFile()
            #self.tracker.receiveDataFile(self.edfFileName, 
            #                             self.edfFileName) 
            self.tracker.close();
            return "Eyelink connection closed successfully"
        else:
            return "Eyelink not available, not closed properly"
 
 
 
 
    ####################################################################
    #    Getting data from the eyetracker
    ####################################################################
 
    def getSample(self, unit=None):
        '''Quickly return the current eye position
            purpose: For use with gaze contingent display experiments
            Note: For speed, this always returns in pixels
        '''
        # check for new sample update:
        sample = self.tracker.getNewestSample() 
        if(sample != None): #Perhapse, change to loop untill sample?
            if self.eye_used == RIGHT_EYE and sample.isRightSample():
                return (np.array(sample.getRightEye().getGaze()) -0.5*self.screenSize) *np.array([1,-1])
            elif self.eye_used == LEFT_EYE and sample.isLeftSample():
                return (np.array(sample.getLeftEye().getGaze()) - 0.5*self.screenSize) * np.array([1,-1])
        return None
 
    def _pix2(pixels, unit = None):
        """Convert size in pixels to size in the default unit for a given Monitor object"""   
        if unit == None: #Use default unit for window
            unit = self.units
        if unit == 'pix':
            return pixels
        if unit == 'cm':
            return psychopy.misc.pix2cm(pixels, self.monitor)
        if unit == 'deg':
            return psychopy.misc.pix2deg(pixels, self.monitor)
 
 
if __name__ == "__main__":
    """Run simple gaze contingent demonstration.
    """
    win = visual.Window(size = (900,700), fullscr=True , allowGUI=False, 
                        color=[-1,-1,-1], units='pix', waitBlanking=True,
                        winType = 'pyglet', monitor='sony',colorSpace='rgb')
    target = visual.PatchStim(win, tex = None, mask = None, 
                              units = 'pix', pos = (0,0), size = (10, 10),  color = [1,1,1])
    note = visual.TextStim(win, pos=[0,0], units = 'pix', text='none', color=(1,1,1))
    clock = core.Clock()
    eyeTracker = TrackerEyeLink(win, clock,doSetup=True)
    status = eyeTracker.getStatus()
    for Ttype in [True, True, True]: #loop for each "trial"
        if Ttype: note.setText("Drift Correct Trial")
        else: note.setText("Standard Trial")
        note.draw()
        win.flip()
        core.wait(1)
        eyeTracker.preTrial(99, Ttype, win)
        #gc.disable()
        done = False
        while not(done): #within-trial loop
            eye_pos = eyeTracker.getSample()
            note.setText( str(eye_pos))
            target.setPos(eye_pos)
            target.draw()
            note.draw()
            win.flip()
            for key in event.getKeys():
                if ( key in ['escape','q'] ) or (eyeTracker.getStatus() != "RECORDING"):
                    win.close()
                    print 'here'
                    eyeTracker.closeConnection()
                    core.quit()
                elif key == 'space':
                    win.flip()
                    print(eyeTracker.getSample())
                    print(clock.getTime())
                    done = True
        eyeTracker.postTrial()
        win.flip()
        #gc.enable()
    win.close()
    eyeTracker.closeConnection()
    print("Self-test completed")
    core.quit()
