"""
wf_netcdfio
-----------

netcdf reading and writing for wflow

$Author: schelle $
$Id: wf_DynamicFramework.py 915 2014-02-10 07:33:56Z schelle $
$Rev: 915 $
"""

import netCDF4
import pyproj
import os


import osgeo.osr as osr

# the two below are needed fpr bbfreeze

try:
    import netCDF4.utils
except:
    import netCDF4_utils

import netcdftime
from pcraster import *
from numpy import *
import time
import datetime as dt
import wflow.wflow_lib as wflow_lib
import wflow.pcrut as _pcrut

globmetadata = {}
globmetadata['title'] = 'wflow output mapstack'
globmetadata['institution'] = 'Deltares'
globmetadata['source'] = 'wflow'
globmetadata['history'] = time.ctime()
globmetadata['references'] = 'https://github.com/openstreams/wflow'
globmetadata['Conventions'] = 'CF-1.4'



def convertCoord(proj_src, proj_trg, x, y):
    """
    Convert a list of x,y pairs in a certain projection to another projection
    input:
        proj_src:   string, EPSG or proj4 string referring to projection of source coordinates
        proj_trg:   string, EPSG or proj4 string referring to projection of target coordinates
        x:          NumPy array, vector or 2D array of x-coordinates (source)
        y:          NumPy array, vector or 2D array of y-coordinates (source)
    output:
        X:          NumPy array, vector or 2D array of x-coordinates (target)
        Y:          NumPy array, vector or 2D array of y-coordinates (target)
    """
    srs1 = pyproj.Proj(proj_src) # OPT['proj4_params'])
    srs2 = pyproj.Proj(proj_trg) # wgs84
    X,Y  = pyproj.transform(srs1, srs2, x,y) # Do add 0. to avoid trunc issues.
    return X,Y


def prepare_nc(trgFile, timeList, x, y, metadata, logger, EPSG="EPSG:4326", units=None,
               calendar='gregorian', Format="NETCDF4", complevel=9, zlib=True, least_significant_digit=None):
    """
    This function prepares a NetCDF file with given metadata, for a certain year, daily basis data
    The function assumes a gregorian calendar and a time unit 'Days since 1900-01-01 00:00:00'
    """
    import datetime as dt

    logger.info('Setting up netcdf output: ' + trgFile)

    if units == None: # Use start of the run
        epoch = timeList[0]
        units = 'seconds since %04d-%02d-%02d %02d:%02d:%02d.0 00:00' % (
        epoch.year, epoch.month, epoch.day, epoch.hour, epoch.minute, epoch.second)

    startDayNr = netCDF4.date2num(timeList[0].replace(tzinfo=None), units=units, calendar=calendar)
    endDayNr = netCDF4.date2num(timeList[-1].replace(tzinfo=None), units=units, calendar=calendar)

    timeAR = linspace(startDayNr, endDayNr, num=len(timeList))
    nc_trg = netCDF4.Dataset(trgFile, 'w', format=Format, zlib=zlib, complevel=complevel)

    logger.info(
        'Setting up dimensions and attributes. Steps: ' + str(len(timeList)) + ' lat: ' + str(len(y)) + " lon: " + str(
            len(x)))
    if len(timeAR) == 1:
        nc_trg.createDimension('time', 1)
    else:
        nc_trg.createDimension('time', 0)  # NrOfDays*8

    DateHour = nc_trg.createVariable('time', 'f8', ('time',), fill_value=-9999., zlib=zlib, complevel=complevel)
    DateHour.units = units
    DateHour.calendar = calendar
    DateHour.standard_name = 'time'
    DateHour.long_name = 'time'
    DateHour.axis = 'T'
    DateHour[:] = timeAR

    # make a proj4 string
    srs = osr.SpatialReference()
    res = srs.ImportFromEPSG(int(EPSG[5:]))
    if res != 0:
        logger.error("EPGS not converted correctly: " + EPSG + ". Is the GDAL_DATA environment variable set correctly?")
        exit(1)

    projStr = srs.ExportToProj4()
    proj_src = '+proj=longlat +ellps=WGS84 +towgs84=0,0,0,0,0,0,0 +no_defs'


    if srs.IsProjected() == 0: # ONly lat lon needed
        nc_trg.createDimension('lat', len(y))
        nc_trg.createDimension('lon', len(x))
        y_var = nc_trg.createVariable('lat', 'f4', ('lat',), fill_value=-9999., zlib=zlib, complevel=complevel)
        y_var.standard_name = 'latitude'
        y_var.long_name = 'latitude'
        y_var.units = 'degrees_north'
        y_var.axis = 'Y'
        x_var = nc_trg.createVariable('lon', 'f4', ('lon',), fill_value=-9999., zlib=zlib, complevel=complevel)
        x_var.standard_name = 'longitude'
        x_var.long_name = 'longitude'
        x_var.units = 'degrees_east'
        x_var.axis = 'X'
        y_var[:] = y
        x_var[:] = x
        crs = nc_trg.createVariable('crs', 'c')
        crs.long_name = 'wgs84'
        crs.proj4_params = '+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs'
        crs.grid_mapping_name = 'latitude_longitude'
    else:  # Assume regular grid in m
        nc_trg.createDimension('y', len(y))
        nc_trg.createDimension('x', len(x))
        y_var = nc_trg.createVariable('y', 'f4', ('y',), fill_value=-9999., zlib=zlib, complevel=complevel)
        y_var.standard_name = 'projection_y_coordinate'
        y_var.long_name = 'y-coordinate in Cartesian system'
        y_var.units = 'm'
        y_var.axis = 'Y'
        x_var = nc_trg.createVariable('x', 'f4', ('x',), fill_value=-9999., zlib=zlib, complevel=complevel)
        x_var.standard_name = 'projection_x_coordinate'
        x_var.long_name = 'x-coordinate in Cartesian system'
        x_var.units = 'm'
        x_var.axis = 'X'
        y_var[:] = y
        x_var[:] = x
        crs = nc_trg.createVariable('crs', 'c')
        crs.long_name = EPSG
        crs.grid_mapping_name = 'universal_transverse_mercator'
        crs.utm_zone_number = srs.GetUTMZone()
        crs.semi_major_axis = srs.GetSemiMajor()
        crs.inverse_flattening = srs.GetInvFlattening()
        crs._CoordinateTransformType = "Projection"
        crs._CoordinateAxisTypes = "y x"
        crs.proj4_params = projStr
        # Also write lat lon fields
        XI,YI = meshgrid(x,y)
        lon_vals,lat_vals = convertCoord(projStr, proj_src, XI, YI)
        # Need to create lat-lon fields
        lat = nc_trg.createVariable('lat','f4',('y','x',))
        lat.standard_name = 'latitude'
        lat.long_name = 'latitude coordinate'
        lat.units = 'degrees_north'
        lat.coordinates = 'lat lon'
        lat.grid_mapping = 'wgs84'
        #lat._CoordinateAxisType = "Lat"
        lat[:,:] = lat_vals
        lon = nc_trg.createVariable('lon','f4',('y','x',))
        lon.standard_name = 'longitude'
        lon.long_name = 'longitude coordinate'
        lon.units = 'degrees_east'
        lon.coordinates = 'lat lon'
        lon.grid_mapping = 'wgs84'
        #lon._CoordinateAxisType = "Lon"
        lon[:,:] = lon_vals

    crs.EPSG_code = EPSG

    # now add all attributes from user-defined metadata
    for attr in metadata:
        nc_trg.setncattr(attr, metadata[attr])
    nc_trg.sync()
    nc_trg.close()


class netcdfoutput():
    def __init__(self, netcdffile, logger, starttime, timesteps, EPSG="EPSG:4326", timestepsecs=86400,
                 metadata={}, zlib=True, Format="NETCDF4",
                 maxbuf=25, least_significant_digit=None):
        """
        Under construction
        """

        self.EPSG = EPSG
        self.zlib = zlib
        self.Format = Format
        self.least_significant_digit = least_significant_digit

        def date_range(start, end, timestepsecs):
                r = int((end + dt.timedelta(seconds=timestepsecs) - start).total_seconds()/timestepsecs)
                return [start + dt.timedelta(seconds=(timestepsecs * i)) for i in range(r)]

        self.logger = logger
        # Do not allow a max buffer larger than the number of timesteps
        self.maxbuf = maxbuf if timesteps >= maxbuf else timesteps
        self.ncfile = netcdffile
        self.timesteps = timesteps
        rows = pcraster._pcraster.clone().nrRows()
        cols = pcraster._pcraster.clone().nrCols()
        cellsize = pcraster._pcraster.clone().cellSize()
        yupper = pcraster._pcraster.clone().north()
        xupper = pcraster._pcraster.clone().west()
        x = _pcrut.pcr2numpy(_pcrut.xcoordinate(_pcrut.boolean(_pcrut.cover(1.0))), NaN)[0, :]
        y = _pcrut.pcr2numpy(_pcrut.ycoordinate(_pcrut.boolean(_pcrut.cover(1.0))), NaN)[:, 0]

        # Shift one timestep as we output at the end
        #starttime = starttime + dt.timedelta(seconds=timestepsecs)
        end = starttime + dt.timedelta(seconds=timestepsecs * (self.timesteps -1))

        timeList = date_range(starttime, end, timestepsecs)
        self.timestepbuffer = zeros((self.maxbuf, len(y), len(x)))
        self.bufflst = {}

        globmetadata.update(metadata)

        prepare_nc(self.ncfile, timeList, x, y, globmetadata, logger, Format=self.Format, EPSG=EPSG,zlib=self.zlib,
                   least_significant_digit=self.least_significant_digit)

    def savetimestep(self, timestep, pcrdata, unit="mm", var='P', name="Precipitation"):
        """
        save a single timestep for a variable

        input:
            - timestep - current timestep
            - pcrdata - pcraster map to save
            - unit - unit string
            - var - variable string
            - name - name of the variable
        """
        # Open target netCDF file
        var = os.path.basename(var)
        self.nc_trg = netCDF4.Dataset(self.ncfile, 'a', format=self.Format, zlib=self.zlib, complevel=9)
        self.nc_trg.set_fill_off()
        # read time axis and convert to time objects
        # TODO: use this to append time
        # time = self.nc_trg.variables['time']
        # timeObj = netCDF4.num2date(time[:], units=time.units, calendar=time.calendar)

        idx = timestep - 1

        buffreset = (idx + 1) % self.maxbuf
        bufpos = (idx) % self.maxbuf

        try:
            nc_var = self.nc_trg.variables[var]
        except:
            self.logger.debug("Creating variable " + var + " in netcdf file. Format: " + self.Format)
            if self.EPSG.lower() == "epsg:4326":
                nc_var = self.nc_trg.createVariable(var, 'f4', ('time', 'lat', 'lon',), fill_value=-9999.0, zlib=self.zlib,
                                                    complevel=9, least_significant_digit=self.least_significant_digit)
                nc_var.coordinates = "lat lon"
            else:
                nc_var = self.nc_trg.createVariable(var, 'f4', ('time', 'y', 'x',), fill_value=-9999.0, zlib=self.zlib,
                                                    complevel=9, least_significant_digit=self.least_significant_digit)
                nc_var.coordinates = "lat lon"
                nc_var.grid_mapping = "crs"

            nc_var.units = unit
            nc_var.standard_name = name
            self.nc_trg.sync()

        miss = float(nc_var._FillValue)
        data = pcr2numpy(scalar(pcrdata), miss)

        if self.bufflst.has_key(var):
            self.bufflst[var][bufpos, :, :] = data
        else:
            self.bufflst[var] = self.timestepbuffer.copy()
            self.bufflst[var][bufpos, :, :] = data

        # Write out timestep buffer.....

        if buffreset == 0 or idx == self.maxbuf - 1 or self.timesteps <= timestep:
            spos = idx - bufpos
            self.logger.debug(
                "Writing buffer for " + var + " to file at: " + str(spos) + " " + str(int(bufpos) + 1) + " timesteps")
            nc_var[spos:idx + 1, :, :] = self.bufflst[var][0:bufpos + 1, :, :]
            self.nc_trg.sync()

    def finish(self):
        """
        Flushes and closes the netcdf file

        :return: Nothing
        """
        if hasattr(self, "nc_trg"):
            self.nc_trg.sync()
            self.nc_trg.close()


class netcdfoutputstatic():
    def __init__(self, netcdffile, logger, starttime, timesteps, EPSG="EPSG:4326", timestepsecs=86400,
                 metadata={}, zlib=True, Format="NETCDF4",
                 maxbuf=25, least_significant_digit=None):
        """
        Under construction
        """

        self.EPSG = EPSG
        self.zlib = zlib
        self.Format = Format
        self.least_significant_digit = least_significant_digit

        def date_range(start, end, timestepsecs):
                r = int((end + dt.timedelta(seconds=timestepsecs) - start).total_seconds()/timestepsecs)
                return [start + dt.timedelta(seconds=(timestepsecs * i)) for i in range(r)]

        self.logger = logger
        # Do not allow a max buffer larger than the number of timesteps
        self.maxbuf = maxbuf if timesteps >= maxbuf else timesteps
        self.ncfile = netcdffile
        self.timesteps = timesteps
        rows = pcraster._pcraster.clone().nrRows()
        cols = pcraster._pcraster.clone().nrCols()
        cellsize = pcraster._pcraster.clone().cellSize()
        yupper = pcraster._pcraster.clone().north()
        xupper = pcraster._pcraster.clone().west()
        x = _pcrut.pcr2numpy(_pcrut.xcoordinate(_pcrut.boolean(_pcrut.cover(1.0))), NaN)[0, :]
        y = _pcrut.pcr2numpy(_pcrut.ycoordinate(_pcrut.boolean(_pcrut.cover(1.0))), NaN)[:, 0]

        # Shift one timestep as we output at the end
        #starttime = starttime + dt.timedelta(seconds=timestepsecs)
        end = starttime + dt.timedelta(seconds=timestepsecs * (self.timesteps -1))

        timeList = date_range(starttime, end, timestepsecs)
        self.timestepbuffer = zeros((self.maxbuf, len(y), len(x)))
        self.bufflst = {}
        self.buffdirty = False

        globmetadata.update(metadata)

        prepare_nc(self.ncfile, timeList, x, y, globmetadata, logger, Format=self.Format, EPSG=EPSG,zlib=self.zlib,
                   least_significant_digit=self.least_significant_digit)


    def savetimestep(self, timestep, pcrdata, unit="mm", var='P', name="Precipitation"):
        """
        save a single timestep for a variable

        input:
            - timestep - current timestep
            - pcrdata - pcraster map to save
            - unit - unit string
            - var - variable string
            - name - name of the variable
        """
        # Open target netCDF file
        var = os.path.basename(var)
        self.nc_trg = netCDF4.Dataset(self.ncfile, 'a', format=self.Format, zlib=self.zlib, complevel=9)
        self.nc_trg.set_fill_off()
        # read time axis and convert to time objects
        # TODO: use this to append time
        # time = self.nc_trg.variables['time']
        # timeObj = netCDF4.num2date(time[:], units=time.units, calendar=time.calendar)

        idx = timestep - 1

        buffreset = (idx + 1) % self.maxbuf
        bufpos = (idx) % self.maxbuf

        try:
            nc_var = self.nc_trg.variables[var]
        except:
            self.logger.debug("Creating variable " + var + " in netcdf file. Format: " + self.Format)
            if self.EPSG.lower() == "epsg:4326":
                nc_var = self.nc_trg.createVariable(var, 'f4', ('time', 'lat', 'lon',), fill_value=-9999.0, zlib=self.zlib,
                                                    complevel=9, least_significant_digit=self.least_significant_digit)
                nc_var.coordinates = "lat lon"
            else:
                nc_var = self.nc_trg.createVariable(var, 'f4', ('time', 'y', 'x',), fill_value=-9999.0, zlib=self.zlib,
                                                    complevel=9, least_significant_digit=self.least_significant_digit)
                nc_var.coordinates = "lat lon"
                nc_var.grid_mapping = "crs"

            nc_var.units = unit
            nc_var.standard_name = name
            self.nc_trg.sync()

        miss = float(nc_var._FillValue)
        data = pcr2numpy(scalar(pcrdata), miss)

        if self.bufflst.has_key(var):
            self.bufflst[var][bufpos, :, :] = data
            self.buffdirty = True
        else:
            self.bufflst[var] = self.timestepbuffer.copy()
            self.bufflst[var][bufpos, :, :] = data
            self.buffdirty = True

        # Write out timestep buffer.....

        if buffreset == 0 or idx == self.maxbuf - 1 or self.timesteps <= timestep:
            spos = idx - bufpos
            self.logger.debug(
                "Writing buffer for " + var + " to file at: " + str(spos) + " " + str(int(bufpos) + 1) + " timesteps")
            nc_var[spos:idx + 1, :, :] = self.bufflst[var][0:bufpos + 1, :, :]
            self.nc_trg.sync()
            self.buffdirty = False

    def finish(self):
        """
        Flushes and closes the netcdf file

        :return: Nothing
        """
        if hasattr(self, "nc_trg"):
            self.nc_trg.sync()
            self.nc_trg.close()
            if self.buffdirty:
                self.logger.error('Finishing with dirty netcdf write buffer...!')


class netcdfinput():
    def __init__(self, netcdffile, logging, vars=[]):
        """
        First try to setup a class read netcdf files
        (converted with pcr2netcdf.py)

        netcdffile: file to read the forcing data from
        logging: python logging object
        vars: list of variables to get from file
        """

        if os.path.exists(netcdffile):
            self.dataset = netCDF4.Dataset(netcdffile, mode='r')
        else:
            logging.error(os.path.abspath(netcdffile) + " not found!")
            exit(ValueError)

        logging.info("Reading input from netCDF file: " + netcdffile + ": " + str(self.dataset).replace('\n', ' '))
        self.alldat = {}
        a = pcr2numpy(cover(0.0), 0.0).flatten()
        # Determine steps to load in mem based on estimated memory usage
        floatspermb = 1048576 / 4
        maxmb = 4000
        self.maxsteps = maxmb * len(a) / floatspermb + 1
        self.fstep = 0
        self.lstep = self.fstep + self.maxsteps

        for var in vars:
            try:
                self.alldat[var] = self.dataset.variables[var][self.fstep:self.maxsteps]
            except:
                self.alldat.pop(var, None)
                logging.warn("Variable " + var + " not found in netcdf file: " + netcdffile)

    def gettimestep(self, timestep, logging, var='P'):
        """
        Gets a map for a single timestep. reads data in blocks assuming sequential access

        timestep: framework timestep (1-based)
        logging: python logging object
        var: variable to get from the file
        """
        ncindex = timestep - 1
        if self.alldat.has_key(var):
            if ncindex == self.lstep:  # Read new block of data in mem
                logging.debug("reading new netcdf data block starting at: " + str(ncindex))
                for vars in self.alldat:
                    self.alldat[vars] = self.dataset.variables[vars][ncindex:ncindex + self.maxsteps]

                self.fstep = ncindex
                self.lstep = ncindex + self.maxsteps
            np_step = self.alldat[var][ncindex - self.fstep, :, :]
            miss = float(self.dataset.variables[var]._FillValue)
            return numpy2pcr(Scalar, np_step, miss), True
        else:
            #logging.debug("Var (" + var + ") not found returning 0")
            return cover(scalar(0.0)), False


class netcdfinputstates():
    def __init__(self, netcdffile, logging, vars=[]):
        """
        First try to setup a class read netcdf files
        (converted with pcr2netcdf.py)

        netcdffile: file to read the forcing data from
        logging: python logging object
        vars: list of variables to get from file
        """

        if os.path.exists(netcdffile):
            self.dataset = netCDF4.Dataset(netcdffile, mode='r')
        else:
            logging.error(os.path.abspath(netcdffile) + " not found!")
            exit(ValueError)

        logging.info("Reading state input from netCDF file: " + netcdffile + ": " + str(self.dataset).replace('\n', ' '))
        self.alldat = {}
        a = pcr2numpy(cover(0.0), 0.0).flatten()
        # Determine steps to load in mem based on estimated memory usage
        floatspermb = 1048576 / 4
        maxmb = 4000
        self.maxsteps = maxmb * len(a) / floatspermb + 1
        self.fstep = 0
        self.lstep = self.fstep + self.maxsteps

        for var in vars:
            try:
                self.alldat[var] = self.dataset.variables[var][self.fstep:self.maxsteps]
            except:
                self.alldat.pop(var, None)
                logging.warn("Variable " + var + " not found in netcdf file: " + netcdffile)

    def gettimestep(self, timestep, logging, var='P'):
        """
        Gets a map for a single timestep. reads data in blocks assuming sequential access

        timestep: framework timestep (1-based)
        logging: python logging object
        var: variable to get from the file
        """
        ncindex = timestep - 1
        if self.alldat.has_key(var):
            if ncindex == self.lstep:  # Read new block of data in mem
                logging.debug("reading new netcdf data block starting at: " + str(ncindex))
                for vars in self.alldat:
                    self.alldat[vars] = self.dataset.variables[vars][ncindex:ncindex + self.maxsteps]
                self.fstep = ncindex
                self.lstep = ncindex + self.maxsteps
            np_step = self.alldat[var][ncindex - self.fstep, :, :]
            miss = float(self.dataset.variables[var]._FillValue)
            return numpy2pcr(Scalar, np_step, miss), True
        else:
            logging.debug("Var (" + var + ") not found returning 0")
            return cover(scalar(0.0)), False


class netcdfinputstatic():
    def __init__(self, netcdffile, logging):
        """
        First try to setup a class read netcdf files
        (converted with pcr2netcdf.py)

        netcdffile: file to read the forcing data from
        logging: python logging object
        vars: list of variables to get from file
        """

        if os.path.exists(netcdffile):
            self.dataset = netCDF4.Dataset(netcdffile, mode='r')
        else:
            logging.error(os.path.abspath(netcdffile) + " not found!")
            exit(ValueError)

        logging.info("Reading static input from netCDF file: " + netcdffile + ": " + str(self.dataset).replace('\n', ' '))



    def gettimestep(self, timestep, logging, var='P'):
        """
        Gets a map for a single timestep. reads data in blocks assuming sequential access

        timestep: framework timestep (1-based)
        logging: python logging object
        var: variable to get from the file
        """

        if self.dataset.variables.has_key(var):
            np_step = self.dataset.variables[var][timestep-1,:,:]
            miss = float(self.dataset.variables[var]._FillValue)
            return numpy2pcr(Scalar, np_step, miss), True
        else:
            logging.debug("Var (" + var + ") not found returning 0")
            return cover(scalar(0.0)), False
