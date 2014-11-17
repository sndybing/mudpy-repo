'''
D. Melgar 02/2014

Forward modeling routines
'''

def waveforms(home,project_name,rupture_name,station_file,model_name,run_name,integrate,tsunami,hot_start,resample,beta):
    '''
    This routine will take synthetics and apply a slip dsitribution. It will delay each 
    subfault by the appropriate rupture time and linearly superimpose all of them. Output
    will be one sac waveform file per direction of motion (NEU) for each station defined in the
    station_file. Depending on the specified rake angle at each subfault the code will compute 
    the contribution to dip and strike slip directions. It will also compute the moment at that
    subfault and scale it according to the unit amount of momeent (1e15 N-m)
    
    IN:
        home: Home directory
        project_name: Name of the problem
        rupture_name: Name of rupture description file
        station_file: File with coordinates of stations
        model_Name: Name of Earth structure model file
        integrate: =0 if you want output to be velocity, =1 if you want output to de displacement
       
    OUT:
        Nothing
    '''
    from numpy import loadtxt,genfromtxt,allclose,vstack,deg2rad,array,sin,cos
    from obspy import read,Stream
    from string import rjust
    import datetime
    import gc
    
    print 'Solving for dynamic problem'
    #Output where?
    outpath=home+project_name+'/output/forward_models/'
    logpath=home+project_name+'/logs/'
    log=''
    #Time for log file
    now=datetime.datetime.now()
    now=now.strftime('%b-%d-%H%M')
    #load source
    source=loadtxt(home+project_name+'/forward_models/'+rupture_name,ndmin=2)
    #Load stations
    station_file=home+project_name+'/data/station_info/'+station_file
    staname=genfromtxt(station_file,dtype="S6",usecols=0)
    #What am I processing v or d ?
    if integrate==1:
        vord='disp'
    else:
        vord='vel'
    #Loop over stations
    for ksta in range(hot_start,len(staname)):
        print 'Working on station '+staname[ksta]+' ('+str(ksta+1)+'/'+str(len(staname))+')'
        #Initalize output
        n=Stream()
        e=Stream()
        z=Stream()
        sta=staname[ksta]
        #Loop over sources (Add delays)
        try:
            for k in range(source.shape[0]):
                if k%100==0:
                    print '... working on parameter '+str(k)+' of '+str(len(source))
                #Get subfault parameters
                nfault='subfault'+rjust(str(int(source[k,0])),4,'0')
                nsub='sub'+rjust(str(int(source[k,0])),4,'0')
                zs=source[k,3]
                ss_slip=source[k,8]
                ds_slip=source[k,9]
                #Rotate
                if beta != None:
                    beta_rot=deg2rad(beta)
                    R=array([[cos(beta_rot),sin(beta_rot)],[-sin(beta_rot),cos(beta_rot)]])
                    rot=R.dot(vstack((ss_slip,ds_slip)))
                    ss_slip=rot[0]
                    ds_slip=rot[1]
                rtime=source[k,12]
                #Where's the data
                strdepth='%.4f' % zs
                if tsunami==False: 
                    syn_path=home+project_name+'/GFs/dynamic/'+model_name+'_'+strdepth+'.'+nsub+'/'
                else:
                    syn_path=home+project_name+'/GFs/tsunami/'+model_name+'_'+strdepth+'.'+nsub+'/'
                #Get synthetics
                ess=read(syn_path+sta+'.'+nfault+'.SS.'+vord+'.e')
                nss=read(syn_path+sta+'.'+nfault+'.SS.'+vord+'.n')
                zss=read(syn_path+sta+'.'+nfault+'.SS.'+vord+'.z')
                eds=read(syn_path+sta+'.'+nfault+'.DS.'+vord+'.e')
                nds=read(syn_path+sta+'.'+nfault+'.DS.'+vord+'.n')
                zds=read(syn_path+sta+'.'+nfault+'.DS.'+vord+'.z')
                #Decide if resampling is required
                if resample!=None:
                    if resample < (1/ess[0].stats.delta): #Downsample
                        ess[0].resample(resample)
                        nss[0].resample(resample)
                        zss[0].resample(resample)
                        eds[0].resample(resample)
                        nds[0].resample(resample)
                        zds[0].resample(resample)
                    elif resample > (1/ess[0].stats.delta): #Upsample
                        upsample(ess,1./resample)
                        upsample(nss,1./resample)
                        upsample(zss,1./resample)
                        upsample(eds,1./resample)
                        upsample(nds,1./resample)
                        upsample(zds,1./resample)
                dt=ess[0].stats.delta
                #Time shift them according to subfault rupture time
                ess=tshift(ess,rtime)
                ess[0].stats.starttime=round_time(ess[0].stats.starttime,dt)
                nss=tshift(nss,rtime)
                nss[0].stats.starttime=round_time(nss[0].stats.starttime,dt)
                zss=tshift(zss,rtime)
                zss[0].stats.starttime=round_time(zss[0].stats.starttime,dt)
                eds=tshift(eds,rtime)
                eds[0].stats.starttime=round_time(eds[0].stats.starttime,dt)
                nds=tshift(nds,rtime)
                nds[0].stats.starttime=round_time(nds[0].stats.starttime,dt)
                zds=tshift(zds,rtime)
                zds[0].stats.starttime=round_time(zds[0].stats.starttime,dt)
                if allclose((ss_slip**2+ds_slip**2)**0.5,0)==False:  #Only add things that matter
                    log=log+nfault+', SS='+str(ss_slip)+', DS='+str(ds_slip)+'\n'
                    #A'ight, add 'em up
                    etotal=add_traces(ess,eds,ss_slip,ds_slip)
                    ntotal=add_traces(nss,nds,ss_slip,ds_slip)
                    ztotal=add_traces(zss,zds,ss_slip,ds_slip)
                    #Add to previous subfault's results
                    e=add_traces(e,etotal,1,1)
                    n=add_traces(n,ntotal,1,1)
                    z=add_traces(z,ztotal,1,1)
                else:
                    log=log+"No slip on subfault "+nfault+', ignoring it...\n'
                gc.collect()
            #Save results
            e.write(outpath+run_name+'.'+sta+'.'+vord+'.e',format='SAC')
            n.write(outpath+run_name+'.'+sta+'.'+vord+'.n',format='SAC')
            z.write(outpath+run_name+'.'+sta+'.'+vord+'.u',format='SAC')
        except:
            print 'An error coccured, skipping station'
    f=open(logpath+'waveforms.'+now+'.log','a')
    f.write(log)
    f.close()
        

def coseismics(home,project_name,rupture_name,station_file):
    '''
    This routine will take synthetics and apply a static slip dsitibution. It will 
    linearly superimpose the synthetic coseismic from each subfault. Output will be
    a single ascii file witht he 3 coseismic offsets (NEU) for each station defined 
    in the station_file. Depending on the specified rake angle at each subfault the 
    code will compute the contribution to dip and strike slip directions. It will 
    also compute the moment at that subfault and scale it according to the unit 
    amount of momeent (1e15 N-m)
    
    IN:
        home: Home directory
        project_name: Name of the problem
        rupture_name: Name of rupture description file
        station_file: File with coordinates of stations
        model_Name: Name of Earth structure model file
       
    OUT:
        Nothing
    '''
    from numpy import loadtxt,genfromtxt,array,savetxt,unique,where
    from string import rjust
    
    print 'Solving for static problem'
    #Output where?
    outpath=home+project_name+'/output/forward_models/'
    #load source
    source=loadtxt(home+project_name+'/forward_models/'+rupture_name,ndmin=2)
    #Load stations
    station_file=home+project_name+'/data/station_info/'+station_file
    staname=genfromtxt(station_file,dtype="S6",usecols=0)
    #Get unique sources
    source_id=unique(source[:,0])
    #Loop over stations
    for ksta in range(len(staname)):
        #Initalize output
        n=array([0])
        e=array([0])
        z=array([0])
        sta=staname[ksta]
        print 'Working on station '+staname[ksta]+' ('+str(ksta+1)+'/'+str(len(staname))+')'
        #Loop over sources
        for k in range(len(source_id)):
            print k
            #Get subfault parameters
            nfault='subfault'+rjust(str(int(source_id[k])),4,'0')
            ifault=where(source[:,0]==source_id[k])[0]
            ss_slip=source[ifault,8].sum()
            ds_slip=source[ifault,9].sum()
            print 'ds_slip='+str(ds_slip)
            #Where's the data
            syn_path=home+project_name+'/GFs/static/'
            #Get synthetics
            coseis_ss=loadtxt(syn_path+sta+'.'+nfault+'.SS.static.neu')
            nss=coseis_ss[0]
            ess=coseis_ss[1]
            zss=coseis_ss[2]
            coseis_ds=loadtxt(syn_path+sta+'.'+nfault+'.DS.static.neu')
            nds=coseis_ds[0]
            eds=coseis_ds[1]
            zds=coseis_ds[2]
            print 'zds='+str(zds)
            #get rake contribution and moment multiplier
            etotal=ds_slip*eds+ss_slip*ess
            ntotal=ds_slip*nds+ss_slip*nss
            ztotal=ds_slip*zds+ss_slip*zss
            print 'ztotal='+str(ztotal)
            #Add to previous subfault's results
            e=e+etotal
            n=n+ntotal
            z=z+ztotal
            print 'n='+str(n)
            print 'e='+str(e)
            print 'z='+str(z)
        #Save results
        savetxt(outpath+sta+'.static.neu',(n,e,z))

def tsunami_waveforms(home,project_name,fault_name,rupture_name,station_file,model_name,run_name,GF_list,G_from_file,G_name,epicenter,
                rupture_speed,num_windows,coord_type,decimate,lowpass,resample,beta):            
    '''
    Forward compute tsunami waveforms the right way, load the GF matrix and just multiply by fault model
    '''
    from mudpy.inverse import getG
    from numpy import genfromtxt,zeros,arange,deg2rad,cos,sin,vstack,array,where
    from obspy import read

    #Read GFs
    G=getG(home,project_name,fault_name,model_name,GF_list,G_from_file,G_name,epicenter,
                rupture_speed,num_windows,coord_type,decimate,lowpass)
    #Read rupture model and convert into vector
    ss=genfromtxt(home+project_name+'/forward_models/'+rupture_name,usecols=8)
    ds=genfromtxt(home+project_name+'/forward_models/'+rupture_name,usecols=9)
    #Rotate by beta
    if beta != None:
        beta_rot=deg2rad(beta)
        R=array([[cos(beta_rot),sin(beta_rot)],[-sin(beta_rot),cos(beta_rot)]])
        rot=R.dot(vstack((ss,ds)))
        ss_rot=rot[0,:]
        ds_rot=rot[1,:]
    #Assemble into column vector
    m=zeros(len(ss)*2)
    iss=arange(0,len(m),2)
    ids=arange(1,len(m),2)
    m[iss]=ss_rot
    m[ids]=ds_rot
    #Multiply
    dtsun=G.dot(m)
    #Write to file (Modified from inverse.write_synthetics)
    #Read gf file and decide what needs to get loaded
    gf_file=home+project_name+'/data/station_info/'+GF_list
    stations=genfromtxt(gf_file,usecols=[0],skip_header=1,dtype='S')
    GF=genfromtxt(gf_file,usecols=[3,4,5,6,7],skip_header=1,dtype='f8')
    GFfiles=genfromtxt(gf_file,usecols=[8,9,10,11,12],skip_header=1,dtype='S')
    #Separate into its constituent parts (statics,displacaments, velocities, etc...)
    kinsert=0
    kgf=3
    i=where(GF[:,kgf]==1)[0]
    if len(i)>0:
        for ksta in range(len(i)):
            sta=stations[i[ksta]]
            tsun=read(GFfiles[i[ksta],kgf])
            npts=tsun[0].stats.npts
            synth=tsun.copy()
            synth[0].data=dtsun[kinsert:kinsert+npts]
            kinsert+=npts
            synth.write(home+project_name+'/output/forward_models/'+run_name+'.'+sta+'.tsun',format='SAC')
            
                        
                                                
def move_seafloor(home,project_name,run_name,model_name,topo_file,topo_dx_file,topo_dy_file,
                tgf_file,fault_name,outname,time_epi,tsun_dt,maxt,ymb,dl=2./60,variance=None,static=False):
    '''
    Create moving topography input files for geoclaw
    '''
    import datetime
    from numpy import genfromtxt,zeros,arange,meshgrid,ones,c_,savetxt,delete
    from obspy import read
    from string import rjust
    from scipy.io import netcdf_file as netcdf
    from scipy.interpolate import griddata
    from mudpy.inverse import interp_and_resample,grd2xyz
    from scipy.ndimage.filters import gaussian_filter

    #Straight line coordinates
    m=ymb[0]
    b=ymb[1]
    #Get station names
    sta=genfromtxt(home+project_name+'/data/station_info/'+tgf_file)
    lon=sta[:,1]
    lat=sta[:,2]
    loni=arange(lon.min(),lon.max()+dl,dl) #Fot grid interpolation
    lati=arange(lat.min(),lat.max()+dl,dl)
    loni,lati=meshgrid(loni,lati)
    #Get fault file
    f=genfromtxt(home+project_name+'/data/model_info/'+fault_name)
    #Where is the data
    data_dir=home+project_name+'/output/forward_models/'
    #Define time deltas
    td_max=datetime.timedelta(seconds=maxt)
    #Maximum tiem to be modeled
    tmax=time_epi+td_max
    #Read derivatives
    bathy_dx=netcdf(topo_dx_file,'r')
    zdx=bathy_dx.variables['z'][:]
    bathy_dy=netcdf(topo_dy_file,'r')
    zdy=bathy_dy.variables['z'][:]
    #Read slope file
    kwrite=0
    idelete=[]
    for ksta in range(len(sta)):
        if ksta%500==0:
            print '... ... working on seafloor grid point '+str(ksta)+' of '+str(len(sta))
        try: #If no data then delete
            if static==False: #We're reading waveforms
                e=read(data_dir+run_name+'.'+rjust(str(int(sta[ksta,0])),4,'0')+'.disp.e')
                n=read(data_dir+run_name+'.'+rjust(str(int(sta[ksta,0])),4,'0')+'.disp.n')
                u=read(data_dir+run_name+'.'+rjust(str(int(sta[ksta,0])),4,'0')+'.disp.z')
                e=interp_and_resample(e,1.0,time_epi)
                n=interp_and_resample(n,1.0,time_epi)
                u=interp_and_resample(u,1.0,time_epi)
                #Keep only data between time_epi and tmax
                e.trim(time_epi,tmax,fill_value=e[0].data[-1],pad=True)
                n.trim(time_epi,tmax,fill_value=n[0].data[-1],pad=True)
                u.trim(time_epi,tmax,fill_value=u[0].data[-1],pad=True)
                #Initalize matrices
                if ksta==0:
                    emat=zeros((n[0].stats.npts,len(sta)))
                    nmat=emat.copy()
                    umat=emat.copy()
                #Populate matrix
                emat[:,kwrite]=e[0].data
                nmat[:,kwrite]=n[0].data
                umat[:,kwrite]=u[0].data
            else:
                neu=genfromtxt(data_dir+rjust(str(int(sta[ksta,0])),4,'0')+'.static.neu')
                n=neu[0]
                e=neu[1]
                u=neu[2]
                tsun_dt=1.0
                maxt=1.0
                if ksta==0:
                    emat=zeros((1,len(sta)))
                    nmat=emat.copy()
                    umat=emat.copy()
                                #Populate matrix
                emat[:,kwrite]=e
                nmat[:,kwrite]=n
                umat[:,kwrite]=u
            kwrite+=1
        except: #Data was missing, delete from lat,lon
            print 'No data for station '+str(ksta)+', deleting from coordinates list'
            idelete.append(ksta)
    #Clean up missing data
    if len(idelete)!=0:
        lat=delete(lat,idelete)
        lon=delete(lon,idelete)
        emat=emat[:,:-len(idelete)]
        nmat=nmat[:,:-len(idelete)]
        umat=umat[:,:-len(idelete)]
    
    #Now go one epoch at a time, and interpolate all fields
    #Get mask for applying horizontal effect
    mask=zeros(loni.shape)
    for k1 in range(loni.shape[0]):
        for k2 in range(loni.shape[1]):
            if (lati[k1,k2]-b)/m>loni[k1,k2]: #Point is to the left, do not apply horizontal effect
                mask[k1,k2]=NaN
    imask1,imask2=where(mask==0)#Points tot he right DO apply horiz. effect
    print '... interpolating coseismic offsets to a regular grid'
    nt_iter=umat.shape[0]
    for kt in range(nt_iter):
        if kt%20==0:
            print '... ... working on time slice '+str(kt)+' of '+str(nt_iter)
        ninterp=griddata((lon,lat),nmat[kt,:],(loni,lati),method='cubic')
        einterp=griddata((lon,lat),emat[kt,:],(loni,lati),method='cubic')
        uinterp=griddata((lon,lat),umat[kt,:],(loni,lati),method='cubic')
        #Output vertical
        uout=uinterp.copy()
        #Apply effect of topography advection
        uout[imask1,imask2]=uout[imask1,imask2]+zdx[imask1,imask2]*einterp[imask1,imask2]+zdy[imask1,imask2]*ninterp[imask1,imask2]
        #print 'no horiz'
        #Filter?
        if variance!=None:
            uout=gaussian_filter(uout,variance)
        #Convert to column format and append
        xyz=grd2xyz(uout,loni,lati)
        tvec=(kt*tsun_dt)*ones((len(xyz),1))
        if kt==0: #Intialize
            numel=uout.size #Number of elements in grid
            kwrite=numel #Where to write the data
            dtopo=zeros((numel*nt_iter,4))
            dtopo[0:kwrite,1:3]=xyz[:,0:2]
        else:
            dtopo[kwrite:kwrite+numel,:]=c_[tvec,xyz]
            kwrite=kwrite+numel
        if static==True:
            tvec=ones(tvec.shape)
            numel=uout.size*2 #Number of elements in grid
            kwrite=numel/2 #Where to write the data
            dtopo=zeros((numel*nt_iter,4))
            dtopo[0:kwrite,1:3]=xyz[:,0:2]
            dtopo[kwrite:kwrite+numel,1:3]=xyz[:,0:2]
            dtopo[kwrite:kwrite+numel,:]=c_[tvec,xyz]
            kwrite=kwrite+numel
    print '... writting dtopo files'
    savetxt(data_dir+outname+'.dtopo',dtopo,fmt='%i\t%.6f\t%.6f\t%.4e')        
            
###########                Tools and trinkets                      #############
    
def get_mu(structure,zs):
    '''
    Look in structure model and compute rigidity given a source depth
    
    IN:
        structure: Array with velocity structure information
        zs: depth in km at which you want to compute mu
        
    OUT:
        mu: Rigidity in Pa
    '''
    from numpy import nonzero
    
    if len(structure)>1: #Model is more than jsut the halfspace
        Z=structure[:,0].cumsum()
        #Which layer do I want?
        i=nonzero(zs>Z)[0]
        if i.size==0: #It's in top layer
            imu=0
        else:
            imu=max(i)+1
        if imu>=structure.shape[0]:
            imu=imu-1#It's int he half-space
        mu=((1000*structure[imu,1])**2)*structure[imu,3]*1000
        #print "Rigidity at z="+str(zs)+' is, mu = '+str(mu/1e9)+'GPa'
    else: #Model is a halfspace
        mu=((1000*structure[0,1])**2)*structure[0,3]*1000
    return mu

def get_source_time_function(mu,area,rise_time,t0,slip):
    '''
    Compute source time function for a given rise time, right now it assumes 1m of slip
    and a triangle STF
    '''
    from numpy import zeros,linspace,where
    
    rise_time=float(rise_time)
    #Initialize outputs
    t=linspace(t0,t0+rise_time,1000)
    Mdot=zeros(t.shape)
    #Triangle gradient
    m=4*mu*area/(rise_time**2)
    #Upwards intercept
    b1=-m*t0
    #Downwards intercept
    b2=m*(t0+rise_time)
    #Assign moment rate
    i=where(t<=t0+rise_time/2)[0]
    Mdot[i]=m*t[i]+b1
    i=where(t>t0+rise_time/2)[0]
    Mdot[i]=-m*t[i]+b2 
    Mdot=Mdot*slip  
    return t,Mdot
    
def add2stf(t1,Mdot1,t2,Mdot2):
    '''
    Add two overlapping source time functions
    '''
    from numpy import interp,linspace
    #Make interpolation vector
    tstart=min(t1[0],t2[0])
    tend=max(t1[-1],t2[-1])
    ti=linspace(tstart,tend,10000)
    #Interpolate
    Mdot1_interp=interp(ti,t1,Mdot1,left=0,right=0)
    Mdot2_interp=interp(ti,t2,Mdot2,left=0,right=0)
    #Add them up
    Mdot_out=Mdot1_interp+Mdot2_interp
    return ti,Mdot_out
    

def add_traces(ss,ds,ssmult,dsmult):
    '''
    Add two stream objects with dip slip and strike slip contributions. This code will take
    two stream objects and super impsoe them according tot he weights defined by ssmult
    dsmult. If one waveform is longer than the other then the code will extend the
    shorter waveform by padding it with the last value.

    For simple addition use ss=ds=M=1
    
    IN:
        ss: Strike slip waveform
        ds: Dip-slip waveform
        ssmult: Strike-slip contribution (meters)
        dsmult: Strike-slip contribution (meters)
    
    OUT:
        st: Stream object with result of superposition
    '''
    from numpy import zeros
    
    #If one stream object is empty set it to zeros, if both are empty then freak out
    if ss.count()==0 and ds.count()==0:
        print 'FATAL ERROR: can\'t add 2 empty stream objects doofus'
        return None
    if ss.count()==0:
        ss=ds.copy()
        ss[0].data=zeros(ds[0].data.shape)
    elif ds.count()==0:
        ds=ss.copy()
        ds[0].data=zeros(ss[0].data.shape) 
        
    #Round times to dt sampling interval
    ss[0].stats.starttime=round_time(ss[0].stats.starttime,ss[0].stats.delta)
    ds[0].stats.starttime=round_time(ds[0].stats.starttime,ds[0].stats.delta)
    #Find earliest starttime
    if ss[0].stats.starttime<=ds[0].stats.starttime:
        t1=ss[0].stats.starttime
    else:
        t1=ds[0].stats.starttime
    #Find altest end time
    if ss[0].stats.endtime>=ds[0].stats.endtime:
        t2=ss[0].stats.endtime
    else:
        t2=ds[0].stats.endtime
    #Now extend both arrays and fill start with zeros then end with last sample
    ss[0].trim(t1,ss[0].stats.endtime,pad=True,fill_value=0)
    ds[0].trim(t1,ds[0].stats.endtime,pad=True,fill_value=0)
    fillend=ss[0].data[-60:-1].mean()
    ss[0].trim(t1,t2,pad=True,fill_value=fillend)
    fillend=ds[0].data[-20:-1].mean()
    ds[0].trim(t1,t2,pad=True,fill_value=fillend)
    #Apply rake scaling value
    ss[0].data=ss[0].data*ssmult
    ds[0].data=ds[0].data*dsmult
    #Creat output stream
    st=ss.copy()
    #Add and apply scale
    st[0].data=ss[0].data+ds[0].data
    #And done
    return st


def tshift(st,tshift):
    '''
    Shift a stream object by tshift seconds, positive moves forward in time
    
    IN:
        st: Stream object
        tshift: Number fo seconds to shift
    OUT:
        st: Shifted stream object
    '''
    from datetime import timedelta
    td=timedelta(seconds=tshift)
    st[0].stats.starttime=st[0].stats.starttime+td
    return st
        
        
def round_time(t1,delta):
    '''
    Round the initial time of a waveform to the nearest multiple of the sampling rate
    IN:
        t1: UTC time object containing start time of waveform
        delta: Sampling interval of waveform in seconds
    OUT:
        t1: Rounded UTC time object
    '''
    from datetime import timedelta
    #Move start and end times to start exactly on the dt intervals
    dtmicro=delta*1e6
    intervals=t1.microsecond/dtmicro #How many intervals in microseconds
    adjustment=(round(intervals)-intervals)*dtmicro
    td=timedelta(microseconds=adjustment)
    t1=t1+td
    return t1

def upsample(st,delta):
    '''
    Go from a low sampling rate to a high sampling rate
    
    IN:
        st - stream object
        delta - sampling rate requested in seconds
    
    OUT:
        st - modified stream object
    '''
    
    from scipy.interpolate import interp1d
    from numpy import arange
    
    t=st[0].times()
    y=st[0].data
    #Make interpolant
    f=interp1d(t,y)
    ti=arange(t[0],t[-1],delta)
    #Interpoalte and reassign tos tream object
    yi=f(ti)
    st[0].data=yi
    st[0].stats.delta=delta

def lowpass(data,fcorner,fsample,order):
    '''
    Make a lowpass zero phase filter
    '''
    from scipy.signal import butter,filtfilt
    from numpy import size,array
    
    if size(fcorner)==2:
        ftype='bandpass'
    else:
        ftype='lowpass'
    fnyquist=fsample/2
    b, a = butter(order, array(fcorner)/(fnyquist),ftype)
    data_filt=filtfilt(b,a,data)
    return data_filt
    
def inv2coulomb(rupt,epicenter,fout):
    '''
    Convert .inv file to Coulomb-ready .inp file
    
    IN:
        rupt - path ro rupture (.inv) file
    '''
    import pyproj
    from numpy import genfromtxt,unique,zeros,where,deg2rad,sin,cos
    
    #Read fault
    f=genfromtxt(rupt)
    #Get total slip by identifying unique fault numbers
    u=unique(f[:,0])
    ss=zeros(len(u))
    ds=zeros(len(u))
    all_ss=f[:,8]
    all_ds=f[:,9]
    for k in range(len(u)):
        i=where(u[k]==f[:,0])
        ss[k]=all_ss[i].sum()
        ds[k]=all_ds[i].sum()
    #Sum them
    slip=(ss**2+ds**2)**0.5
    #Get rake
    rake=ssds2rake(ss,ds)
    #Convert coordinate subfault centers to local cartesian
    g = pyproj.Geod(ellps='WGS84') # Use WGS84 ellipsoid.
    x=zeros(len(u))
    y=zeros(len(u))
    for k in range(len(u)):
        baz,az,d=pyproj.Geod.inv(g,f[k,1],f[k,2],epicenter[0],epicenter[1])
        x[k]=(d/1000)*sin(deg2rad(az))
        y[k]=(d/1000)*cos(deg2rad(az))
    #Get width and length to get coordiantes of top corners and strike,dip
    width=f[:,10]/1000
    length=f[:,11]/1000
    strike=f[:,4]
    dip=f[:,5]
    depth=f[:,3]
    top_mid_x=zeros(len(u))
    top_mid_y=zeros(len(u))
    top_direction=strike-90 #This is the angle that points towards the top edge of the fault
    xstart=zeros(len(u))
    ystart=zeros(len(u))
    xfin=zeros(len(u))
    yfin=zeros(len(u))
    ztop=zeros(len(u))
    zbot=zeros(len(u))
    for k in range(len(u)):
        top_mid_x[k]=x[k]+((width[k]/2)*cos(deg2rad(dip[k])))*sin(deg2rad(top_direction[k]))
        top_mid_y[k]=y[k]+((width[k]/2)*cos(deg2rad(dip[k])))*cos(deg2rad(top_direction[k]))
        xstart[k]=top_mid_x[k]+(width[k]/2)*sin(deg2rad(strike[k]-180))
        ystart[k]=top_mid_y[k]+(width[k]/2)*cos(deg2rad(strike[k]-180))
        xfin[k]=top_mid_x[k]+(width[k]/2)*sin(deg2rad(strike[k]))
        yfin[k]=top_mid_y[k]+(width[k]/2)*cos(deg2rad(strike[k]))
        ztop[k]=depth[k]-(length[k]/2)*sin(deg2rad(dip[k]))
        zbot[k]=depth[k]+(length[k]/2)*sin(deg2rad(dip[k]))
    #Write to file and then manually add the ehaders and footers by copy pasting from some NEIC file (LAZY!)
    f=open(fout,'w')
    for k in range(len(u)):
        out='1   %10.4f %10.4f %10.4f %10.4f 100 %10.4f %10.4f %10.4f %10.4f %10.4f %i\n' % (xstart[k],ystart[k],xfin[k],yfin[k],rake[k],slip[k],dip[k],ztop[k],zbot[k],k)
        f.write(out)
    f.close()
    
def coulomb_xy2latlon(f,epicenter,fout):
    '''
    Change the x-y coordinates of a Coulomb file to lat/lon
    '''
    from numpy import genfromtxt,zeros,rad2deg,arctan,isnan,savetxt
    import pyproj
    
    s=genfromtxt('/Users/dmelgarm/bin/coulomb34/output_files/Element_conditions_tohoku_fine.csv')
    x=s[:,1]
    y=s[:,2]
    #Now use pyproj to dead reckon anf get lat/lon coordinates of subfaults
    g = pyproj.Geod(ellps='WGS84')
    #first get azimuths of all points, go by quadrant
    az=zeros(x.shape)
    for k in range(len(x)):
        if x[k]>0 and y[k]>0:
            az[k]=rad2deg(arctan(x[k]/y[k]))
        if x[k]<0 and y[k]>0:
            az[k]=360+rad2deg(arctan(x[k]/y[k]))
        if x[k]<0 and y[k]<0:
            az[k]=180+rad2deg(arctan(x[k]/y[k]))
        if x[k]>0 and y[k]<0:
            az[k]=180+rad2deg(arctan(x[k]/y[k]))
    #Quadrant correction
    #Now horizontal distances
    d=((x**2+y**2)**0.5)*1000
    #Now reckon
    lo=zeros(len(d))
    la=zeros(len(d))
    for k in range(len(d)):
        if isnan(az[k]): #No azimuth because I'm on the epicenter
            print 'Point on epicenter'
            lo[k]=epicenter[0]
            la[k]=epicenter[1]
        else:
            lo[k],la[k],ba=g.fwd(epicenter[0],epicenter[1],az[k],d[k])
    s[:,1]=lo
    s[:,2]=la
    savetxt(fout,s)
    
    
      
def ssds2rake(ss,ds):
    '''
    Compute rake angle in degrees
    '''
    from numpy import arctan,rad2deg,pi,zeros
    try:
        rake=zeros(len(ss))
    except:
        rake=zeros(1)
    for k in range(len(rake)):
        if ss[k]>0 and ds[k]>0:
            rake[k]=arctan(ds[k]/ss[k])
        elif ds[k]>0 and ss[k]<0:
            rake[k]=pi+arctan(ds[k]/ss[k])
        elif ds[k]<0 and ss[k]<0:
            rake[k]=pi+arctan(ds[k]/ss[k])
        elif ds[k]<0 and ss[k]>0:
            rake[k]=2*pi+arctan(ds[k]/ss[k])
    rake=rad2deg(rake)
    return rake
    
def makefault(strike,dip,nstrike,ndip,rake,dx_dip,dx_strike,epicenter,num_updip,num_downdip,fout):
    '''
    Make a planar fault
    '''
    from numpy import arange,sin,cos,deg2rad,r_,ones,arctan,rad2deg,zeros,isnan,unique,where,argsort
    import pyproj
    
    strike=163
    dip=74
    proj_angle=180-strike #Angle to use for sin.cos projection (comes from strike)
    y=arange(-nstrike/2+1,nstrike/2+1)*dx_strike
    x=arange(-nstrike/2+1,nstrike/2+1)*dx_strike
    z=ones(x.shape)*epicenter[2]
    y=y*cos(deg2rad(strike))
    x=x*sin(deg2rad(strike))
    #Move up 7 slots
    #x=x-x[15]
    #y=y-y[15]
    
    #Save teh zero line
    y0=y.copy()
    x0=x.copy()
    z0=z.copy()
    #Initlaize temp for projection up/down dip
    xtemp=x0.copy()
    ytemp=y0.copy()
    ztemp=z0.copy()
    #Get delta h and delta z for up/ddx_dip=1own dip projection
    dh=dx_dip*cos(deg2rad(dip))
    dz=dx_dip*sin(deg2rad(dip))
    #Project updip lines
    for k in range(num_updip):
        xtemp=xtemp+dh*cos(deg2rad(proj_angle))
        ytemp=ytemp+dh*sin(deg2rad(proj_angle))
        ztemp=ztemp-dz
        x=r_[x,xtemp]
        y=r_[y,ytemp]
        z=r_[z,ztemp]
    #Now downdip lines
    xtemp=x0.copy()
    ytemp=y0.copy()
    ztemp=z0.copy()
    for k in range(num_downdip):
        xtemp=xtemp-dh*cos(deg2rad(proj_angle))
        ytemp=ytemp-dh*sin(deg2rad(proj_angle))
        ztemp=ztemp+dz
        x=r_[x,xtemp]
        y=r_[y,ytemp]
        z=r_[z,ztemp]
    #Now use pyproj to dead reckon anf get lat/lon coordinates of subfaults
    g = pyproj.Geod(ellps='WGS84')
    #first get azimuths of all points, go by quadrant
    az=zeros(x.shape)
    for k in range(len(x)):
        if x[k]>0 and y[k]>0:
            az[k]=rad2deg(arctan(x[k]/y[k]))
        if x[k]<0 and y[k]>0:
            az[k]=360+rad2deg(arctan(x[k]/y[k]))
        if x[k]<0 and y[k]<0:
            az[k]=180+rad2deg(arctan(x[k]/y[k]))
        if x[k]>0 and y[k]<0:
            az[k]=180+rad2deg(arctan(x[k]/y[k]))
    #Quadrant correction
    #Now horizontal distances
    d=((x**2+y**2)**0.5)*1000
    #Now reckon
    lo=zeros(len(d))
    la=zeros(len(d))
    for k in range(len(d)):
        if isnan(az[k]): #No azimuth because I'm on the epicenter
            print 'Point on epicenter'
            lo[k]=epicenter[0]
            la[k]=epicenter[1]
        else:
            lo[k],la[k],ba=g.fwd(epicenter[0],epicenter[1],az[k],d[k]) 
    #Sort them from top right to left along dip
    zunique=unique(z)
    for k in range(len(zunique)):
        i=where(z==zunique[k])[0] #This finds all faults at a certain depth
        isort=argsort(la[i]) #This sorths them south to north
        if k==0: #First loop
            laout=la[i][isort]
            loout=lo[i][isort]
            zout=z[i][isort]
        else:
            laout=r_[laout,la[i][isort]]
            loout=r_[loout,lo[i][isort]]
            zout=r_[zout,z[i][isort]]
    #Write to file
    strike=ones(loout.shape)*strike
    dip=ones(loout.shape)*dip
    tw=ones(loout.shape)*0.5
    rise=ones(loout.shape)*1
    L=ones(loout.shape)*1000
    W=ones(loout.shape)*1000
    f=open(fout,'w')
    for k in range(len(x)):   
        out='%i\t%.6f\t%.6f\t%.3f%i\t%i\t%.1f\t%.1f\t%.2f\t%.2f\n' % (k,loout[k],laout[k],zout[k],strike[k],dip[k],tw[k],rise[k],L[k],W[k])
        f.write(out)
    f.close()
    
    
def make_checkerboard(rupt,nstrike,ndip,fout,nwin):
    '''
    Make checekrboard for resolution analysis
    '''
    from numpy import genfromtxt,unique,arange,union1d,savetxt
   
    f=genfromtxt(rupt)
    u=unique(f[:,0])
    f=f[0:len(u),:]
    #Set strike-slip/dip_slip to zero
    f[:,8]=0
    f[:,9]=0
    #1 and 2
    i1=arange(0,nstrike,4)
    i2=arange(1,nstrike,4)
    i=union1d(i1,i2)
    j1=arange(21,2*nstrike,4)
    j2=arange(22,2*nstrike,4)
    j=union1d(j1,j2)
    ij=union1d(i,j)
    f[ij,9]=1
    # 3 and 4
    i1=arange(44,3*nstrike,4)
    i2=arange(45,3*nstrike,4)
    i=union1d(i1,i2)
    j1=arange(65,4*nstrike,4)
    j2=arange(66,4*nstrike,4)
    j=union1d(j1,j2)
    ij=union1d(i,j)
    f[ij,9]=1
    # 5 and 6
    i1=arange(84,5*nstrike,4)
    i2=arange(85,5*nstrike,4)
    i=union1d(i1,i2)
    j1=arange(105,6*nstrike,4)
    j2=arange(106,6*nstrike,4)
    j=union1d(j1,j2)
    ij=union1d(i,j)
    f[ij,9]=1
    # 7 and 8
    i1=arange(128,7*nstrike,4)
    i2=arange(129,7*nstrike,4)
    i=union1d(i1,i2)
    j1=arange(149,8*nstrike,4)
    j2=arange(150,8*nstrike,4)
    j=union1d(j1,j2)
    ij=union1d(i,j)
    f[ij,9]=1
    # 9
    i1=arange(168,9*nstrike,4)
    i2=arange(169,9*nstrike,4)
    ij=union1d(i1,i2)
    f[ij,9]=1
    #Write to file
    fmt='%6i\t%.4f\t%.4f\t%8.4f\t%.2f\t%.2f\t%.2f\t%.2f\t%12.4e\t%12.4e%10.1f\t%10.1f\t%8.4f\t%.4e'
    savetxt(fout,f,fmt)
    
def model_resolution(Gfile,outdir,fault,nwindows,Ls,Lt,lambda_s,lambda_t):
    '''
    Compute model resolution matrix and output to GMT plottable file
    '''
    from numpy import load,diag,arange,zeros,genfromtxt,savetxt,c_,r_,eye
    from scipy.linalg import inv
    
    #read fault model
    lon=genfromtxt(fault,usecols=1)
    lat=genfromtxt(fault,usecols=2)
    nfaults=len(lon)
    nfaults_total=nfaults*nwindows*2
    #G=load(Gfile)
    ##Tsunami weights
    #W=eye(G.shape[0])
    #W[4302:,4302:]=W[4302:,4302:]*2
    #W=W*1.1
    #G=W.dot(G)
    ##
    #Vel weights
    #W=eye(G.shape[0])*4.5
    #G=W.dot(G)
    #
    ##Combine everything
    Gdisp=load(Gfile_disp)
    Gvel=load(Gfile_vel)
    W=eye(Gvel.shape[0])*4.5
    Gvel=W.dot(Gvel)
    #Gtsun=load(Gfile_tsun)
    #W=eye(Gtsun.shape[0])
    #W[4302:,4302:]=W[4302:,4302:]*2
    #W=W*1.1
    #Gtsun=W.dot(Gtsun)
    G=r_[Gdisp,Gvel]
    Gdisp=Gvel=None
    LsLs=Ls.T.dot(Ls)
    #LtLt=Lt.T.dot(Lt)
    #R=(inv(G.T.dot(G)+(lambda_s**2)*LsLs+(lambda_t**2)*LtLt).dot(G.T)).dot(G)
    R=(inv(G.T.dot(G)+(lambda_s**2)*LsLs).dot(G.T)).dot(G)
    r=diag(R)
    R=None
    rout=zeros(nfaults)
    #Go one subfault at a time average ss and ds individually then average total ss and total ds
    #for k in range(nfaults):
    #    iss=arange(2*k,nfaults_total,nfaults)
    #    ids=arange(2*k+1,nfaults_total,nfaults)
    #    rss=r[iss].mean()
    #    rds=r[ids].mean()
    #    #rout[k]=max([rss,rds])
    #    rout[k]=rds
    rout=r[arange(1,len(r),2)]
    fout=Gfile.split('/')[-1]
    fout=outdir+fout.split('.')[0]+fout.split('.')[1]+'.R'
    savetxt(fout,c_[lon,lat,rout],fmt='%10.6f\t%10.6f\t%8.4f')
    
def trim_add_noise(data_path,checker_path,search_pattern):
    '''
    Trim checkerboard data and Add gaussian noise to data
    
    data_path='/Volumes/Kanagawa/Slip_Inv/tohoku_10s/data/waveforms/'
    search_pattern='checker.*disp*'
    checker_path='/Volumes/Kanagawa/Slip_Inv/tohoku_10s/output/forward_models/'    
    '''
    from numpy import var
    from numpy.random import normal
    from glob import glob
    from obspy import read
    
    checker_files=glob(checker_path+search_pattern)
    for k in range(len(checker_files)):
        ch=read(checker_files[k])
        #Find corresponding data file
        sta=checker_files[k].split('/')[-1].split('.')[1]
        vord=checker_files[k].split('/')[-1].split('.')[2]
        comp=checker_files[k].split('/')[-1].split('.')[3]
        data_file=glob(data_path+sta+'*'+vord+'*'+comp)
        st=read(data_file[0])
        ch.trim(starttime=st[0].stats.starttime,endtime=st[0].stats.endtime)
        #determine variance
        v=2e-5 #vel
        noise=normal(loc=0.0, scale=v**0.5, size=ch[0].stats.npts)
        ch[0].data=ch[0].data+noise
        ch.write(checker_files[k],format='SAC')