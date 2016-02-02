# Tobii controller for PsychoPy
# author: Matus Simkovic
# backbone of the code provided by Hiroyuki Sogo

import os, datetime, time
try:
    import tobii.eye_tracking_io.mainloop
    import tobii.eye_tracking_io.browsing
    import tobii.eye_tracking_io.eyetracker
    import tobii.eye_tracking_io.time.clock
    import tobii.eye_tracking_io.time.sync
    from tobii.eye_tracking_io.types import Point2D, Blob
    from tobii.eye_tracking_io.basic import EyetrackerException
except ImportError:
    print 'Warning: Tobii import Failed'
        
from threading import Thread
from psychopy.sound import SoundPygame
from psychopy.core import Clock
from psychopy.misc import deg2pix
from psychopy import visual, event
import numpy as np
import sys,os
def myCm2deg(cm,dist): return cm/(dist*0.017455) 

# here are some constants, settings and helper functions
class ETSTATUS():
    OFF, FOUND, CREATED, SETUPFINISHED,CALSTARTED, CALFAILED,CALSUCCEEDED, CALRECEIVED, CALACCEPTED, TRACKING=range(10)
    toString = ('Not Found', 'Found', 'Connected', 'Finished Setup','Started Calibration',
        'Calibration Failed','Calibration was Successful', 'Received Calibration Data', 
        'Calibration Accepted', 'Tracking Finished')
class Settings():
    """ I put here everything I considered worth varying"""
    
    stimPath=os.path.abspath(__file__).rsplit(os.path.sep,1)[0]+os.path.sep+'stimuli'+os.path.sep #stimulus path
    calStimPath = stimPath+'spiral.png' # path of the calibration picture
    dcorrStimPath=stimPath+'clover.png' # path of the drift correction picture (= attention catcher)
    soundStimPath=stimPath+'6.ogg' # path of the sound stimulus
    fsizebig=0.05 # size of the big font in norm units
    fsizesmall=0.02 # size of the small font in norm units
    drawcolor='white'# font and line color
    wincolor='gray' # background color
    calPointDuration=2 # presentation duration of each calibration point in seconds
    afterCalib=2 #in seconds, duration of the pause after each calibration point
    psychopyClock=Clock() # default clock
    eyeRadius=0.01# radius of the circle indicating eye position during setup and cal in norm units
    validity2color=['red','yellow','white','green'] # color representing the validity code
    # text labels and their position for setup 
    txtLabelsSetup=[ ['Bird-eye View',[0.5,0.95] , fsizebig] ,  ['Side View',[0.5,-0.05] , fsizebig] ,
        ['Front View',[-0.5,-0.05] , fsizebig], ['Front View Relative',[-0.5,0.95] ,fsizebig] ]
    # fixation extraction
    THETA=0.6; # parameter for online exponential smoothing AR(1) filter
    FIXVTH=18 # upper velocity threshold for fixations in deg per sec
    FIXMINDUR=0.1 # minimum fixation duration in seconds
    FUSS=5 # sample size over which the average fixation target position is computed
    BLINKTOL=5 # minimum nr of consecutive blink data required to interupt a fixation
    # functions for translation of the head movement box to screen coordinates 
    centerz=600 # distance in mm from screen
    scaling=0.002 # mm to norm display units [-1,1] ratio
    @staticmethod
    def ucsz2norm(z):
        return (z-Settings.centerz)*Settings.scaling
    @staticmethod
    def ucsxy2norm(xy):
        return xy*Settings.scaling
    
class TobiiController: 
    
    def __init__(self, win,getfhandle,sid=0,block=0,verbose=False,fin=None,fout=''):
        """ Initialize controller window, connect and activate eyetracker
            win - supply a window where the experiment is shown
            sid - subject id
            block - block nr, for experiments with several blocks
            fn - file name TC from data
        """
        self.etstatus=ETSTATUS.OFF
        self.sid=sid
        self.block=block
        self.getf=getfhandle
        self.verbose=verbose
        self.fin=fin
        self.target=None
        self.eyetracker = None
        self.eyetrackers = {}
        self.win = win # this window is where the experiment is displayed to subject
        # and here we display information from the controller to the experimenter
        self.win2=visual.Window(monitor='tobii',color=Settings.wincolor,
            fullscr=False,size=(640,512),units='deg')#,pos=(30,30))
        self.gazeData = [] # we collect gaze data supplied by eyetracker
        self.curTime=[] # we monitor and save the time of the arrival of the gaze data
        self.eventData = [] # and we collect events here
        self.datafile = None
        # main menu vars
        self.msg=visual.TextStim(self.win2,height=Settings.fsizebig,units='norm',
                    color=Settings.drawcolor, text='')
        # calibration vars
        self.calin = visual.Circle(self.win,radius=2,fillColor=Settings.drawcolor,units='pix')
        self.calout=visual.ImageStim(self.win,image=Settings.calStimPath,size=(200,200),units='pix')
        self.calGrid=np.array([[1,0,1],[0,1,0],[1,0,1]])
        self.soundStim=SoundPygame(value=Settings.soundStimPath)
        self.soundStim.setVolume(1)
        # drift correction vars
        self.dcorrstim=visual.ImageStim(self.win,
            image=Settings.dcorrStimPath,size=(200,200),units='pix')
        self.init_eyetracker()
        self.gazeData = []
        self.curTime=[]
        self.eventData = []
        self.setDataFile(fout+'VP%03dB%d.csv'%(self.sid,self.block))

    def init_eyetracker(self):
        # lets start, initialize, find and activate the eyetracker
        tobii.eye_tracking_io.init()
        self.clock = tobii.eye_tracking_io.time.clock.Clock()
        self.mainloop_thread = tobii.eye_tracking_io.mainloop.MainloopThread()
        self.mainloop_thread.start()
        self.browser = tobii.eye_tracking_io.browsing.EyetrackerBrowser(self.mainloop_thread, 
            self.on_eyetracker_browser_event)
        while not self.etstatus==ETSTATUS.FOUND:
            time.sleep(0.01)
        self.activate(self.eyetrackers.keys()[0]) # by default we take the first eyetracker found
        self.hz=self.eyetracker.GetFramerate()
        
    def on_eyetracker_browser_event(self, event_type, event_name, eyetracker_info):
        # When a new eyetracker is found we add it to the treeview and to the 
        # internal list of eyetracker_info objects
        if event_type == tobii.eye_tracking_io.browsing.EyetrackerBrowser.FOUND:
            self.etstatus=ETSTATUS.FOUND
            self.eyetrackers[eyetracker_info.product_id] = eyetracker_info
            return False
        
        # Otherwise we remove the tracker from the treeview and the eyetracker_info list...
        del self.eyetrackers[eyetracker_info.product_id]
        if len(self.eyetrackers)==0: self.etstatus=ETSTATUS.OFF
        
        # ...and add it again if it is an update message
        if event_type == tobii.eye_tracking_io.browsing.EyetrackerBrowser.UPDATED:
            self.eyetrackers[eyetracker_info.product_id] = eyetracker_info
        return False
        
    def destroy(self):
        self.eyetracker = None
        self.browser.stop()
        self.browser = None
        self.mainloop_thread.stop()
        
    ############################################################################
    # activation methods
    ############################################################################
    def activate(self,eyetracker):
        eyetracker_info = self.eyetrackers[eyetracker]
        print "Connecting to:", eyetracker_info
        tobii.eye_tracking_io.eyetracker.Eyetracker.create_async(self.mainloop_thread,
            eyetracker_info,lambda a,b: self.on_eyetracker_created(a,b,eyetracker_info))
        
        while not self.etstatus==ETSTATUS.CREATED:
            time.sleep(0.01)
        self.syncmanager = tobii.eye_tracking_io.time.sync.SyncManager(self.clock,eyetracker_info,self.mainloop_thread)
        
    def on_eyetracker_created(self, error, eyetracker, eyetracker_info):
        if error:
            print "  Connection to %s failed because of an exception: %s" % (eyetracker_info, error)
            if error == 0x20000402:
                print "The selected unit is too old, a unit which supports protocol version 1.0 is required.\n\n<b>Details:</b> <i>%s</i>" % error
            else:
                print "Could not connect to %s" % (eyetracker_info)
            return False
        
        self.etstatus=ETSTATUS.CREATED
        self.eyetracker = eyetracker
        
    ############################################################################
    # mainscreen methods
    ############################################################################
    def doMain(self):
        if not self.etstatus>=ETSTATUS.CREATED:
            print 'doMain >> eyetracker not connected'
            return False
        self.msg.setText('Welcome to Tobii\n\tEyetracker Status: %s\n' %ETSTATUS.toString[self.etstatus]
            +'Type:\n\tS - show setup screen \n\tC - calibrate \n\tE - run Experiment \n\tESC - Abort')
        while True: # stay within the main section until experiment starts
            self.msg.draw()
            self.win2.flip()
            for key in event.getKeys():
                if 's' == key: self.doSetup()
                elif 'c' == key: 
                    self.doCalibration(stimulus=self.target,calibrationGrid=self.calGrid)
                    self.msg.setText('Welcome to Tobii\n\tEyetracker Status: '+
                        '%s\n' %ETSTATUS.toString[self.etstatus]+'Type:\n\tS - show'+
                        ' setup screen \n\tC - calibrate \n\tE - run Experiment \n\tESC - Abort')
                elif 'e' == key: return # start experiment
                elif 'escape' == key: # abort
                    self.win2.close()
                    self.win.close()
                    self.destroy()
                    sys.exit()
                else: 'TODO'
            time.sleep(0.01)
            
    ############################################################################
    # setup methods
    ############################################################################
    def doSetup(self):
        ''' press escape to return to main menu, press s to play sound'''
        if self.etstatus<ETSTATUS.CREATED:
            print 'doSetup >> eyetracker not connected'
            return False
        #elif not self.etstatus==ETSTATUS.SETUPFINISHED:
        self.initSetupGraphics()
            
        self.startTracking()
        self.win2.flip()
        finished=False
        while not finished: # track data until escape is pressed
            if len(self.gazeData)==0: continue
            gd= self.gazeData[-1]
            # left eye side view
            self.eyes[0].setPos([Settings.ucsz2norm(gd.LeftEyePosition3D.z)+self.offset,
                Settings.ucsxy2norm(gd.LeftEyePosition3D.y)-self.offset])
            self.eyes[0].setFillColor(Settings.validity2color[gd.LeftValidity-1])
            self.eyes[0].setLineColor(Settings.validity2color[gd.LeftValidity-1])
            # right eye side view
            self.eyes[1].setPos([Settings.ucsz2norm(gd.RightEyePosition3D.z)+self.offset,
                Settings.ucsxy2norm(gd.RightEyePosition3D.y)-self.offset])
            self.eyes[1].setFillColor(Settings.validity2color[gd.RightValidity-1])
            self.eyes[1].setLineColor(Settings.validity2color[gd.RightValidity-1])
            
            # left eye bird-eye view
            self.eyes[2].setPos([Settings.ucsz2norm(gd.LeftEyePosition3D.z)+self.offset,
                Settings.ucsxy2norm(gd.LeftEyePosition3D.x)+self.offset])
            self.eyes[2].setFillColor(Settings.validity2color[gd.LeftValidity-1])
            self.eyes[2].setLineColor(Settings.validity2color[gd.LeftValidity-1])
            # right eye bird-eye view
            self.eyes[3].setPos([Settings.ucsz2norm(gd.RightEyePosition3D.z)+self.offset,
                Settings.ucsxy2norm(gd.RightEyePosition3D.x)+self.offset])
            self.eyes[3].setFillColor(Settings.validity2color[gd.RightValidity-1])
            self.eyes[3].setLineColor(Settings.validity2color[gd.RightValidity-1])
            # left eye front view
            self.eyes[4].setPos([Settings.ucsxy2norm(gd.LeftEyePosition3D.x)-self.offset,
                Settings.ucsxy2norm(gd.LeftEyePosition3D.y)-self.offset])
            self.eyes[4].setFillColor(Settings.validity2color[gd.LeftValidity-1])
            self.eyes[4].setLineColor(Settings.validity2color[gd.LeftValidity-1])
            # right eye front view
            self.eyes[5].setPos([Settings.ucsxy2norm(gd.RightEyePosition3D.x)-self.offset,
                Settings.ucsxy2norm(gd.RightEyePosition3D.y)-self.offset])
            self.eyes[5].setFillColor(Settings.validity2color[gd.RightValidity-1])
            self.eyes[5].setLineColor(Settings.validity2color[gd.RightValidity-1])
            # left eye front view relative
            self.eyes[6].setPos([(gd.LeftEyePosition3DRelative.x-0.5)*0.5-self.offset,
                -(gd.LeftEyePosition3DRelative.y-0.5)*0.4+self.offset])
            self.eyes[6].setFillColor(Settings.validity2color[gd.LeftValidity-1])
            self.eyes[6].setLineColor(Settings.validity2color[gd.LeftValidity-1])
            # right eye front view relative
            self.eyes[7].setPos([(gd.RightEyePosition3DRelative.x-0.5)*0.5-self.offset,
                -(gd.RightEyePosition3DRelative.y-0.5)*0.4+self.offset])
            self.eyes[7].setFillColor(Settings.validity2color[gd.RightValidity-1])
            self.eyes[7].setLineColor(Settings.validity2color[gd.RightValidity-1])
            self.screenshot.draw()
            for i in range(len(self.eyes)): 
                if ((i % 2)==0 and not((gd.LeftEyePosition3D.x, 
                        gd.LeftEyePosition3D.y,gd.LeftEyePosition3D.z )==(0,0,0))  or 
                    (i % 2)==1 and not((gd.RightEyePosition3D.x, 
                        gd.RightEyePosition3D.y,gd.RightEyePosition3D.z )==(0,0,0)) ):
                    self.eyes[i].draw()
            self.win2.flip()
            for key in event.getKeys():
                if key=='escape': finished=True
                if key=='s': self.soundStim.play()
        event.clearEvents()
        self.stopTracking(flush=False)
        self.etstatus=ETSTATUS.SETUPFINISHED
        
    def initSetupGraphics(self):
        # we need to obtain the head movement box data
        self.hmb=None
        self.eyetracker.GetTrackBox(self.onHeadMovementBox)
        while self.hmb==None: time.sleep(0.01)
        hmbStim=[]
        offset=self.offset=0.5 # in norm display units [-1,1]
        # top trapezoid
        vertices=np.array([[self.hmb.Point1.z,self.hmb.Point1.x],[self.hmb.Point2.z,self.hmb.Point2.x],
            [self.hmb.Point6.z,self.hmb.Point6.x],[self.hmb.Point5.z,self.hmb.Point5.x]])
        vertices[:,0]=Settings.ucsz2norm(vertices[:,0]); vertices[:,1]=Settings.ucsxy2norm(vertices[:,1]); 
        vertices[:,0]+=offset;  vertices[:,1]+=offset;  
        hmbStim.append(visual.ShapeStim(self.win2,vertices=vertices,units='norm',lineColor=Settings.drawcolor))
        
        # with T60 the bottom trapezoid is the same as the top trapezoid, hence we skipp it here
        
        # left trapezoid
        vertices=np.array([[self.hmb.Point6.z,self.hmb.Point6.y],[self.hmb.Point2.z,self.hmb.Point2.y],
            [self.hmb.Point3.z,self.hmb.Point3.y],[self.hmb.Point7.z,self.hmb.Point7.y]])
        vertices[:,0]=Settings.ucsz2norm(vertices[:,0]); vertices[:,1]=Settings.ucsxy2norm(vertices[:,1]); 
        vertices[:,0]+=offset;  vertices[:,1]-=offset;  
        hmbStim.append(visual.ShapeStim(self.win2,vertices=vertices,units='norm',lineColor=Settings.drawcolor))
        
        # with T60 the left trapezoid is the same as the right trapezoid, hence we skipp it here
        
        #front rectangle
        vertices=np.array([[self.hmb.Point6.x,self.hmb.Point6.y],[self.hmb.Point5.x,self.hmb.Point5.y],
            [self.hmb.Point8.x,self.hmb.Point8.y],[self.hmb.Point7.x,self.hmb.Point7.y]])
        vertices=Settings.ucsxy2norm(vertices); vertices[:,0]-=offset;  vertices[:,1]-=offset;  
        hmbStim.append(visual.ShapeStim(self.win2,vertices=vertices,units='norm',lineColor=Settings.drawcolor))
        
        # back rectangle
        vertices=np.array([[self.hmb.Point1.x,self.hmb.Point1.y],[self.hmb.Point4.x,self.hmb.Point4.y],
            [self.hmb.Point3.x,self.hmb.Point3.y],[self.hmb.Point2.x,self.hmb.Point2.y]])
        vertices=Settings.ucsxy2norm(vertices); vertices[:,0]-=offset;  vertices[:,1]-=offset;  
        hmbStim.append(visual.ShapeStim(self.win2,vertices=vertices,units='norm',lineColor=Settings.drawcolor))
        
        # front rectangle relative position
        hmbStim.append(visual.Rect(self.win2,width=0.5, height=0.4,units='norm',pos=[-offset,offset],lineColor=Settings.drawcolor))

        for t in Settings.txtLabelsSetup:
            hmbStim.append(visual.TextStim(self.win2,text=t[0],pos=t[1],height=t[2],units='norm',color=Settings.drawcolor))
        self.screenshot=visual.BufferImageStim(self.win2, stim=hmbStim)
        
        self.eyes=[]
        for i in range(8):  self.eyes.append(visual.Circle(self.win2,units='norm',radius=Settings.eyeRadius))
        
    def onHeadMovementBox(self,error,response):
        if not error: self.hmb = response
        else: print 'GetHeadMovementBox failed: ', error
        
    ############################################################################
    # calibration methods
    ############################################################################
    
    def doCalibration(self, paced=True,calibrationGrid=np.ones((3,3)),
        stimulus=None,soundStim=None, shrinkingSpeed=1.5, rotationSpeed=-2):
        ''' paced - if True calibration at each point is initiated by key press (space),
                   othwerwise a fixed time onset is used
            calibrationGrid - 2D numpy array with ones and zeros as elements,
                specifies the location of calibration points on a equally spaced grid (ones are drawn)
            stimulus - ShapeStim instance, allows you to provide the visual stimulus, 
                by default the stimulus prespecified in Settings is used
            soundStim - psychopy.sound.SoundPygame instance, allows you to provide the sound stimulus,
                by default the stimulus prespecified in Settings is used
            shrinkingSpeed - speed of shrinking of the stimulus
            rotationSpeed - rotation speed of the stimulus
        '''
        self.calin = visual.Circle(self.win,radius=2,fillColor=Settings.drawcolor,units='pix')
        self.calout=visual.ImageStim(self.win,image=Settings.calStimPath,size=(200,200),units='pix')
        self.calGrid=np.array([[1,0,1],[0,1,0],[1,0,1]])
        self.calPointsAdded=0
        if soundStim!=None: self.soundStim = stimulus
        if self.etstatus<ETSTATUS.CREATED:
            print 'doCalibration >> eyetracker not connected'
            return False
            
        if stimulus!=None: self.calout = stimulus
        self.msg.setPos((0,-0.25),units='norm')
            
        self.datafile.write("Calibration Start\n")
        self.eyetracker.StartCalibration(self.on_calib_start)
        while self.etstatus<ETSTATUS.CALSTARTED:
            time.sleep(0.01)
        self.win2.flip()
        self.win.flip()
        time.sleep(1)
        # determine the point position
        dy=1.0/calibrationGrid.shape[1]
        dx=1.0/calibrationGrid.shape[0]
        points=[]
        for x in range(calibrationGrid.shape[0]):
            for y in range(calibrationGrid.shape[1]):
                if calibrationGrid[y,x]: points.append((x,y))
        initSize=np.copy(self.calout.size)
        circs= [visual.Circle(self.win2,radius=2,fillColor=Settings.drawcolor,units='pix'),
            visual.Circle(self.win2,radius=0.01,fillColor='green',units='norm'),
            visual.Circle(self.win2,radius=0.01,fillColor='red',units='norm')]
        # calibrate
        for pindex in np.random.permutation(len(points)):# randomize point order
            # draw point and play sound
            x,y=points[pindex]
            p = Point2D()
            p.x=(x+0.5)*dx
            p.y=(y+0.5)*dy
            self.calin.setPos(((p.x-0.5)*self.win.size[0],(0.5-p.y)*self.win.size[1]))
            self.calout.setPos(((p.x-0.5)*self.win.size[0],(0.5-p.y)*self.win.size[1]))
            self.soundStim.play() 
            self.soundStim.fadeOut(Settings.calPointDuration*1000)
            Settings.psychopyClock.reset()
            if not paced: # show for a fixed duration
                while Settings.psychopyClock.getTime() < Settings.calPointDuration:
                    if self.calout.size[0]>1: self.calout.setSize(self.calout.size-shrinkingSpeed,units='pix')
                    self.calout.setOri(self.calout.ori+rotationSpeed)
                    self.calout.draw()
                    self.calin.draw()
                    self.win.flip()
                
                target=self.calPointsAdded + 1
                self.eyetracker.AddCalibrationPoint(p,self.on_add_completed)
                while self.calPointsAdded<target:
                    self.calin.draw()
                    self.win.flip()
            else:
                finished=False; rep=1
                self.startTracking() # we will track the fixation accuracy
                while not finished:
                    if self.calout.size[0]-shrinkingSpeed<0 or self.calout.size[0]-shrinkingSpeed> initSize[0]: 
                        shrinkingSpeed= - shrinkingSpeed
                    self.calout.setSize(self.calout.size-shrinkingSpeed,units='pix')
                    self.calout.setOri(self.calout.ori+rotationSpeed)
                    gz=self.getCurrentGazePosition(eyes=2,units='norm')
                    if rep==10 and gz is not None:  # display feedback every ten frames
                        #self.msg.setText('left: %f    right: %f, %f, %f' %(gz[0],gz[1],(p.x-0.5)*2,(0.5-p.y)*2) )
                        #self.msg.draw()
                        if  not np.isnan(gz[0]): 
                            #circs[1].setPos(( -(p.x-0.5)*2+gz[0],-(0.5-p.y)*2+gz[1] ) )# left eye
                            circs[1].setPos( (-(p.x-0.5)*2+gz[0],-(0.5-p.y)*2+gz[1]) )
                            circs[1].draw()
                        if  not np.isnan(gz[2]): 
                            circs[2].setPos( (-(p.x-0.5)*2+gz[2],-(0.5-p.y)*2+gz[3]) )# right eye
                            circs[2].draw()
                        circs[0].draw()
                        #for pnt in circs: pnt.draw()
                        #print gz
                        self.win2.flip() # note this flip will postpone win.flip() below, waitBlanking=False window flag doesn't work with two monitors
                    rep= rep%10 +1
                    self.calout.draw()
                    self.calin.draw()
                    self.win.flip()
                    for key in event.getKeys():
                        if key=='space': finished=True
                        if key=='escape': 
                            self.stopTracking(flush=False)
                            self.eyetracker.StopCalibration(None)
                            return
                self.stopTracking(flush=False)
                target=self.calPointsAdded + 1
                self.eyetracker.AddCalibrationPoint(p,self.on_add_completed)
                while self.calPointsAdded<target:
                    if self.calout.size[0]>1: 
                        self.calout.setSize(self.calout.size-shrinkingSpeed,units='pix')
                    self.calout.setOri(self.calout.ori+rotationSpeed)
                    self.calout.draw()
                    self.calin.draw()
                    self.win.flip()
            
            self.win.flip()
            time.sleep(Settings.afterCalib)
            self.calout.setSize(initSize)
        
        self.eyetracker.ComputeCalibration(self.on_calib_compute)
        while self.etstatus<=ETSTATUS.CALSTARTED:
            time.sleep(0.01)
        self.eyetracker.StopCalibration(None)
        self.win.flip()

        
        if self.etstatus<ETSTATUS.CALSUCCEEDED:
            #computeCalibration failed.
            self.msg.setText('Not enough data was collected \n\tR - retry\n\tESC - back to main menu')
        else: 
            #lets look at the results
            self.calib = self.eyetracker.GetCalibration(self.on_calib_response)
            while self.etstatus<ETSTATUS.CALRECEIVED:
                time.sleep(0.01)
            if self.calib == None:
                #no calibration data
                self.msg.setText('No calibration data \n\tR - retry\n\tESC - back to main menu')
            else:
                stimuli=[]
                points = {}
                for data in self.calib.plot_data:
                    points[data.true_point] = {'left':data.left, 'right':data.right}
                if len(points) == 0:
                    self.msg.setText('No calibration data\n\tR - retry\n\tESC - back to main menu')
                else:
                    for p,d in points.iteritems():
                        self.datafile.write('Point, x=%.4f, y=%.4f\t'%(p.x,p.y))
                        self.datafile.write('Left '+str(d['left'])+'\t')
                        self.datafile.write('Right '+str(d['right'])+'\n')
                        if d['left'].status == 1:
                            stimuli.append(visual.Line(self.win2,lineColor='red',
                                start= (2*p.x-1,1-2*p.y), units='norm',
                                end= (d['left'].map_point.x*2-1,1- d['left'].map_point.y*2)))
                        if d['right'].status == 1:
                            stimuli.append(visual.Line(self.win2,lineColor='green',
                                start= (2*p.x-1,1-2*p.y), units='norm',
                                end= (d['right'].map_point.x*2-1,1- d['right'].map_point.y*2)))
                #print 'len stimuli: ',len(stimuli)
                self.calresult=visual.BufferImageStim(self.win2,stim=stimuli)
                self.calresult.draw()
                self.msg.setText('Accept calibration results?\n\tA - accept\n\tR - retry\n\tESC - back to main menu')
        
        self.msg.draw()
        self.win2.flip()
        event.clearEvents()
        # we are finished what should we do next?
        waitkey = True
        while waitkey:
            for key in event.getKeys():
                if key == 'a':
                    self.etstatus=ETSTATUS.CALACCEPTED
                    waitkey=False
                    self.datafile.write("Calibration Accepted\n")
                elif key == 'r':
                    self.etstatus=ETSTATUS.SETUPFINISHED
                    self.doCalibration(stimulus=stimulus,calibrationGrid=calibrationGrid)
                    waitkey=False
                elif key=='d':
                    self.calresult.draw()
                    self.msg.draw()
                    self.win2.flip()
                elif key == 'escape':
                    self.etstatus=ETSTATUS.SETUPFINISHED
                    waitkey=False
        self.datafile.write("Calibration Finished\n")
    
    def on_calib_start(self, error, r):
        if error:
            print "Could not start calibration because of error. (0x%0x)" % error
            self.datafile.write("Could not start calibration because of error. (0x%0x)\n" % error)
            return False
        self.etstatus=ETSTATUS.CALSTARTED
    
    def on_add_completed(self, error, r):
        if error:
            print "Add Calibration Point failed because of error. (0x%0x)" % error
            self.datafile.write("Add Calibration Point failed because of error. (0x%0x)\n" % error)
            return False
        self.calPointsAdded += 1
        return False
    
    def on_calib_compute(self, error, r):
        if error == 0x20000502:
            print "CalibCompute failed because not enough data was collected:", error
            print "Not enough data was collected during calibration procedure."
            self.datafile.write("Not enough data was collected during calibration procedure.\n")
            self.etstatus=ETSTATUS.CALFAILED
            return False
        elif error != 0:
            print "CalibCompute failed because of a server error:", error
            print "Could not compute calibration because of a server error.\n\n<b>Details:</b>\n<i>%s</i>" % (error)
            self.datafile.write( "Could not compute calibration because of a server error.\n\n<b>Details:</b>\n<i>%s</i>\n" % (error) )
            self.etstatus=ETSTATUS.CALFAILED
            return False
        else:
            print "CalibCompute Success"
            self.etstatus=ETSTATUS.CALSUCCEEDED
        
    def on_calib_response(self, error, calib):
        if error:
            print "On_calib_response: Error =", error
            self.calib = None
            self.datafile.write("On_calib_response: Error\n")
            return False
        print "On_calib_response: Success"
        self.datafile.write("On_calib_response: Success\n")
        self.calib = calib
        self.etstatus=ETSTATUS.CALRECEIVED
    
    
    def on_calib_done(self, status, msg):
        # When the calibration procedure is done we update the calibration plot
        if not status: print msg
        self.calibration = None
        return False
    ############################################################################
    #  drift correction methods
    ############################################################################
    def doDriftCorrection(self,stimulus=None,soundStim=None, shrinkingSpeed=1.5, rotationSpeed=-2):
        ''' in principle this part could be used for drift correction since the stimulus
            appears at the screen center, but with infants we use it to bring the attention
            of the infant back to the screen
            stimulus - ShapeStim instance, allows you to provide the visual stimulus, 
                by default the stimulus prespecified in Settings is used
            soundStim - psychopy.sound.SoundPygame instance, allows you to provide the sound stimulus,
                by default the stimulus prespecified in Settings is used
            shrinkingSpeed - speed of shrinking of the stimulus
            rotationSpeed - rotation speed of the stimulus
        '''
        if soundStim!=None: self.soundStim = stimulus
        self.calin.setPos((0,0))
        self.calout.setPos((0,0))
        Settings.psychopyClock.reset()
        self.soundStim.play()
        rs=rotationSpeed
        ss=shrinkingSpeed
        initori=np.copy(self.dcorrstim.ori)
        inits=np.copy(self.dcorrstim.size)
        self.sendMessage('Drift Correction')
        # show until the infant is looking (anywhere) on the screen, but at least for Settings.calPointDuration sec 
        while Settings.psychopyClock.getTime() < Settings.calPointDuration or np.isnan(self.getCurrentGazePosition()[0]):
            self.dcorrstim.setSize(self.dcorrstim.size-ss,units='pix')
            if np.abs(inits[0]-self.dcorrstim.size[0])>20: ss= -ss
            self.dcorrstim.setOri(self.dcorrstim.ori+rs)
            if np.abs(initori-self.dcorrstim.ori)>70: rs= -rs
            self.dcorrstim.draw()
            self.win.flip()
            for key in event.getKeys():
                if key== 'escape': 
                    self.win2.close()
                    self.win.close()
                    self.destroy()
                    sys.exit()
        self.soundStim.stop()
        self.dcorrstim.setSize(inits)
        self.dcorrstim.setOri(initori)
        
    ############################################################################
    # tracking methods
    ############################################################################
    
    def startTracking(self):
        # fixation extraction vars
        self.fixBlinkCount=0
        self.fixloc=np.array((np.nan,np.nan))
        self.fixsum=np.array((np.nan,np.nan))
        self.fixdur=0
        #self.eyetracker.events.OnGazeDataReceived += self.onGazedata
        self.eyetracker.StartTracking(self.onGazedata)
    
    def stopTracking(self,flush=True):
        ''' flush - True: write the data to output file, False: discard data '''
        self.eyetracker.StopTracking()
        #self.eyetracker.events.OnGazeDataReceived -= self.onGazedata
        if flush: self.flushData()
        self.curTime=[]
        self.gazeData = []
        self.eventData = []
        
    
    def getGazePosition(self,index,eyes=1,units='norm'):
        ''' returns the gaze postion of the data specified by index
            if coordinates are not available or invalid, returns nan values
            index - self.gazeData index, e.g. -1 returns the last sample
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
        if len(self.gazeData)==0: return np.ones( eyes*2)*np.nan
        g=self.gazeData[index]
        out= [g.LeftGazePoint2D.x*xscale-xscale/2.0, 
                -g.LeftGazePoint2D.y*yscale+yscale/2.0,
                g.RightGazePoint2D.x*xscale-xscale/2.0, 
                -g.RightGazePoint2D.y*yscale+yscale/2.0]
        if g.LeftValidity>3: out[0]=np.nan; out[1]=np.nan;
        if g.RightValidity>3: out[2]=np.nan; out[3]=np.nan;
        if eyes==2: return np.array(out)
        avg=[(out[0]+out[2])/2.0, (out[1]+out[3])/2.0]
        #if g.LeftValidity>3: avg[0]=out[2];avg[1]=out[3];
        #if g.RightValidity>3: avg[0]=out[0];avg[1]=out[1];
        if g.LeftValidity>3 or g.RightValidity>3: avg=[np.nan,np.nan,np.nan,np.nan]
        return np.array(avg)
        
    def getCurrentGazePosition(self,eyes=1,units='norm'):
        ''' returns the current gaze postion
            if coordinates are not available or invalid, returns nan values
            eyes - 1: average coordinates of both eye are return as ndarray with 2 elements
                    2: coordinates of both eyes are returned as ndarray with 4 elements
            units - units of output coordinates
                    'norm', 'pix', 'cm' and 'deg' are currently supported
        '''
        return self.getGazePosition(-1,eyes=eyes,units=units)
            
        
    def onGazedata(self,error,gaze):
        ''' receives callbacks from eyetracker when new data are available
            and computes smoothed gaze position and extracts fixations
        '''
        self.gazeData.append(gaze)
        self.curTime.append([self.clock.get_time(),self.getf()])
        if Settings.FIXVTH==0: return
        else: self.computeFixation()
        
    def computeFixation(self,cgp=None):
        if cgp is None: # if no argument is provided set to current gaze pos
            cgp=self.getCurrentGazePosition(eyes=1,units='deg')
        if np.isnan(cgp[0]): # no data, handle blinks
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
        gc=self.getCurrentGazePosition(units=units)
        fd=self.fixdur/self.hz
        fc=self.fixsum/float(Settings.FUSS)#/float(max(self.fixdur,1))
        if units is 'cm': fc=deg2cm(fc, self.win.monitor)
        elif units is 'pix': fc=deg2pix(fc, self.win.monitor)
        elif units is 'norm': fc = deg2pix(fc, self.win.monitor) / self.win.size*2
        return gc,fc, fd>Settings.FIXMINDUR,0
        

    def setDataFile(self,filename):
        print 'Set datafile ' + filename
        self.datafile = open(filename,'a')
        self.datafile.write('Recording date:\t'+datetime.datetime.now().strftime('%Y/%m/%d')+'\n')
        self.datafile.write('Recording time:\t'+datetime.datetime.now().strftime('%H:%M:%S')+'\n')
        self.datafile.write('Subject: \t%d\nBlock: \t%d\n'%(self.sid,self.block))
        self.datafile.write('Recording resolution\t%d x %d\n' % tuple(self.win.size))
        self.datafile.write('Monitor Distance\t%f\n'% self.win.monitor.getDistance())
        self.datafile.write('Monitor Width\t%f\n'% self.win.monitor.getWidth())
        self.datafile.write('Recording refresh rate: \t%d\n'%self.hz)
        self.datafile.write('\t'.join(['TimeStamp','Frame', 'GazePointXLeft', 'GazePointYLeft',
            'ValidityLeft', 'GazePointXRight', 'GazePointYRight', 'ValidityRight',
            'Lag','PupilLeft', 'PupilRight' ])+'\n')
        
    def closeDataFile(self):
        print 'Datafile closed'
        if self.datafile != None and len(self.gazeData)>0: self.flushData(); self.datafile.close()
        self.datafile = None
        
    def sendMessage(self,event):
        if self.verbose: print event
        t = self.syncmanager.convert_from_local_to_remote(self.clock.get_time())
        self.eventData.append((t,self.getf(),event))
        
    def flushData(self):
        ''' writes data to output file, output format is similar to tobii studio output'''
        if self.datafile == None: print 'data file is not set.'; return
        self.datafile.write('Recording time:\t'+datetime.datetime.now().strftime('%H:%M:%S')+'\n')
        if len(self.gazeData)==0: return
        timeStampStart = self.gazeData[0].Timestamp
        t0=-1000;eind=0; i=-1
        for g in self.gazeData:
            i+=1; t1=(g.Timestamp-timeStampStart)/1000.0
            if eind<len(self.eventData):# write events at the correct time position 
                e = self.eventData[eind]
                et=(e[0]-timeStampStart)/1000.0
                if et>t0 and et<t1: self.datafile.write('%.3f\t%d\t%s\n' % (et,e[1],e[2])); eind+=1
            self.datafile.write('%.3f\t%d\t%.4f\t%.4f\t%d\t%.4f\t%.4f\t%d\t%.3f\t%.4f\t%.4f\n'%(t1,
                self.curTime[i][1],
                g.LeftGazePoint2D.x*self.win.size[0] if g.LeftValidity!=4 else -1.0,
                g.LeftGazePoint2D.y*self.win.size[1] if g.LeftValidity!=4 else -1.0,
                g.LeftValidity,
                g.RightGazePoint2D.x*self.win.size[0] if g.RightValidity!=4 else -1.0,
                g.RightGazePoint2D.y*self.win.size[1] if g.RightValidity!=4 else -1.0,
                g.RightValidity, (self.curTime[i][0]-self.syncmanager.convert_from_remote_to_local(g.Timestamp))/1000.0,
                g.LeftPupil if g.LeftValidity!=4 else -1.0,
                g.RightPupil if g.RightValidity!=4 else -1.0))
        while eind <len(self.eventData): # write any remaining events
            e = self.eventData[eind]
            et=(e[0]-timeStampStart)/1000.0
            self.datafile.write('%.3f\t%d\t%s\n' % (et,e[1],e[2]))
            eind+=1
        self.datafile.flush()
    ############################################################################
    # high-level methods for eyetracker control
    ############################################################################
    def preTrial(self,driftCorrection=True):
        self.startTracking()
        if driftCorrection: self.doDriftCorrection()
        else:
            t0=Settings.psychopyClock.getTime()
            while Settings.psychopyClock.getTime()-t0<0.2:
                self.win.flip()
        
    def postTrial(self):
        self.stopTracking()
    
    def closeConnection(self):
        self.closeDataFile()
        self.destroy()

############################################################################

# Dummy eyetracker & Tobii controller that loads data from a file
############################################################################

    
class DummyVector():
    def __init__(self,x,y):
        self.x=x;self.y=y
class DummyPoint2D():
    def __init__(self,ts,lx,ly,lv,rx,ry,rv,lp,rp):
        self.Timestamp=ts*1000000
        self.LeftGazePoint2D=DummyVector(lx,ly)
        self.RightGazePoint2D=DummyVector(rx,ry)
        self.LeftValidity=lv;self.RightValidity=rv
        self.LeftPupil=lp;self.RightPupil=rp
def loadData(fin):
    ''' fin - filepath '''
    #print fin
    f=open(fin,'r')
    data=[];start=False
    for line in f.readlines():
        cols=line.rsplit('\t')
        if cols[0]=='Recording refresh rate: ':
            hz=float(cols[1])
        if cols[0]=='Recording resolution':
            w,h=cols[1].rsplit(' x ')
            w=float(w);h=float(h)
            print 'res',w,h
        if line[:15]=='Recording time:' and start:
            start=False
        if len(cols)>2 and cols[2]=='Trial':
            if len(data):
                data[-1]=np.array(data[-1])
                data[-1][:,0]-=data[-1][0,0];data[-1][:,0]/=1000.
                for i in [2,3,5,6]:
                    sel=data[-1][:,i]==-1
                    data[-1][sel,i]=np.nan
                data[-1][:,[2,5]]/=w;data[-1][:,[3,6]]/=h
            #t0=float(cols[0])
            data.append([]);start=True
        if start and len(cols)==11: data[-1].append(map(float,cols))
    f.close()
    data[-1]=np.array(data[-1])
    data[-1][:,0]-=data[-1][0,0];data[-1][:,0]/=1000.
    for i in [2,3,5,6]:
        sel=data[-1][:,i]==-1
        data[-1][sel,i]=np.nan
    data[-1][:,[2,5]]/=w;data[-1][:,[3,6]]/=h
    return data,hz
class DummyClock():
    def __init__(self):
        self.t0=time.time()


class DummyEyetracker(Thread):
    def start(self,fin):
        self.trial=0;self.index=0
        self.makedata=0;self.destroyFlag=False
        self.data,self.hz=loadData(fin)
        self.events=DummyVector(0,0)# any object will do
        self.events.OnGazeDataReceived=[]
        self.tracking=False
        Thread.start(self)
        return self.hz
    def convert_from_remote_to_local(self,time): return time
    def convert_from_local_to_remote(self,time): return time
    def get_time(self): return (time.time()-self.t0)*1000000
        
    def run(self):
        inc=1/float(self.hz)
        while self.trial<len(self.data):
            if self.destroyFlag: break
            #print 'loopstart'
            if not self.tracking:
                #print 'not tracking'
                time.sleep(0.01)
                continue
            if self.index>=self.data[self.trial].shape[0]:
                self.makedata+=1
                tt=self.data[self.trial][-1,0]+inc*self.makedata
                p=DummyPoint2D(tt,np.nan,np.nan,4,np.nan,np.nan,4,0,np.nan)
                self.ongazeData(None,p)
                time.sleep(inc)
                #print 'no more data'
                continue
            if self.data[self.trial][self.index,0]<0:
                raise ValueError
            diff=(time.time()-self.t0)-self.data[self.trial][self.index,0]
            if diff>0:
                #print 'difsleep',self.trial,self.index,self.data[self.trial][self.index,2]
                p=DummyPoint2D(*self.data[self.trial][self.index,[0,2,3,4,5,6,7,9,10]].tolist())
                self.ongazeData(None,p)
                self.index+=1
            else:
                time.sleep(-diff+0.0001)
                #print -diff,self.trial,time.time()-self.t0,self.index,self.data[self.trial][self.index,0]
        print 'finished'
    def StartTracking(self,callback):
        print 'start tracking',self.trial
        self.ongazeData=callback
        self.tracking=True
        self.t0=time.time()
    def StopTracking(self):
        if self.trial<len(self.data):
            
            dr=self.data[self.trial][self.index:,2]
            print 'stop tracking', dr.shape[0],(~np.isnan(dr)).sum()
            if (~np.isnan(dr)).sum()>10:
                self.data[self.trial]=self.data[self.trial][self.index:,:]
                self.data[self.trial][:,0]-=self.data[self.trial][0,0]
            else: self.trial+=1 
        else:
            print 'stop tracking'
            self.trial+=1;
        self.tracking=False;self.makedata=0;self.index=0;
    def destroy(self):
        self.destroyFlag=True
        
class TobiiControllerFromOutput(TobiiController):
    def init_eyetracker(self):
        self.eyetracker=DummyEyetracker()
        self.hz=self.eyetracker.start(self.fin)
        self.clock=self.eyetracker
        self.syncmanager=self.eyetracker
        #self.etstatus=ETSTATUS.CREATED
    def destroy(self):
        self.eyetracker.destroy()
        self.eyetracker = None
    def doDriftCorrection(self):
        Settings.psychopyClock.reset()
        self.sendMessage('Drift Correction')
    def preTrial(self,driftCorrection=True):
        self.startTracking()
        if driftCorrection: self.doDriftCorrection()
    
if __name__ == "__main__":
    # following demo shows the performance of the online fixation detection algorithm
    import sys
    f=0
    win = visual.Window(size=(1280,1024),pos=(0,0),fullscr=True,units='deg',monitor='tobii',screen=1)
    controller = TobiiController(win,lambda: f)
    controller.doMain()
    controller.preTrial()
    # fixation point marker
    marker = visual.Circle(win,radius=2,lineColor=Settings.drawcolor,units='pix',
        fillColor='yellow',interpolate=False)
    waitkey = True
    fixdur =0
    while waitkey:
        gd,cgp,isf,more = controller.getCurrentFixation(units='pix')
        if isf: fixdur+=1
        else: fixdur=1
        if not np.isnan(cgp[0]): 
            marker.setPos(cgp)
            marker.setRadius(fixdur/5.0)
        for key in event.getKeys():
            if key=='space':
                waitkey=False
            elif key=='w':
                controller.sendMessage('w key')
        marker.draw()
        win.flip()
        f+=1
    
    controller.postTrial()
    win.close()
    controller.closeConnection()
