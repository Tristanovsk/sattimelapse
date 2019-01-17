# coding=utf-8
import os
import sys
import numpy as np
from esasnappy import GPF
from esasnappy import jpy
from esasnappy import ProductUtils
from dateutil import parser


class info:
    def __init__(self, product, sensordata):
        #########################
        # settings:
        #########################
        # to use AERONET data for aerosol optical thickness
        # self.aeronet = True
        self.aeronet = False

        #########################
        # variables:
        #########################
        self.product = product
        self.headerfile = ""
        self.sensor = ""
        self.l2_product = None
        self.aux = None
        self.date = ""
        self.width = 0
        self.height = 0
        self.name = ""
        self.description = ""
        self.band_names = ""
        self.N = 0
        self.wl = []
        self.b = []
        self.sza = []
        self.sazi = []
        self.vza = []
        self.vazi = []
        self.wkt = []  # geographical extent in POLYGON format
        self.outfile = ""
        self.aeronetfile = ""
        self.pressure_ref = 1015.20
        self.pressure = 1015.2
        self.ssp = 1015.2
        self.aot550 = 0.1
        self.aot = []
        self.angstrom = 1
        self.fcoef = 0.5
        self.rot = []
        self.oot = []
        self.solar_irr = []
        self.U = 1.

        # data type for pixel values
        self.type = np.float32

        ### Define filtering thresholds
        self.hcld_threshold = 3e-3

    def set_outfile(self, file):
        self.outfile = file

    def set_aeronetfile(self, file):
        self.aeronetfile = file

    def get_product_info(self):
        product = self.product
        self.width = product.getSceneRasterWidth()
        self.height = product.getSceneRasterHeight()
        self.name = product.getName()
        self.description = product.getDescription()
        # self.band_names = product.getBandNames()
        self.date = parser.parse(str(product.getStartTime()))

    def get_bands(self, band_names=['B1']):
        '''get wavelengths, bands, geometries'''
        product = self.product
        self.band_names = band_names
        self.N = len(band_names)
        N = range(self.N)
        self.VZA = [[] for i in N]
        self.VAZI = [[] for i in N]
        self.B = [[] for i in N]
        self.wl = [0 for i in N]
        # self.mvza = product.getBand('view_zenith_mean')
        # self.mazi = product.getBand('view_azimuth_mean')
        self.SZA = product.getBand('sun_zenith')
        self.SAZI = product.getBand('sun_azimuth')
        # self.SZA.loadRasterData()
        # self.SAZI.loadRasterData()

        for i in N:
            self.B[i] = product.getBand(band_names[i])
            self.wl[i] = self.B[i].getSpectralWavelength()
            self.VZA[i] = product.getBand('Zenith_' + band_names[i])
            self.VAZI[i] = product.getBand('Azimuth_' + band_names[i])
            # self.B[i].loadRasterData()
            # self.VZA[i].loadRasterData()
            # self.VAZI[i].loadRasterData()

    def load_data(self, rownum):
        from multiprocessing import Pool
        from contextlib import closing
        # construct arrays
        self.hcld = np.zeros(self.width, dtype=self.type, order='F')
        self.rs2 = [np.zeros(self.width, dtype=self.type) for i in range(self.N)]
        self.vza = [np.zeros(self.width, dtype=self.type) for i in range(self.N)]
        self.razi = [np.zeros(self.width, dtype=self.type) for i in range(self.N)]
        self.sza = np.zeros(self.width, dtype=self.type, order='F')
        self.sazi = np.zeros(self.width, dtype=self.type, order='F')
        self.muv = [np.zeros(self.width, dtype=self.type) for i in range(self.N)]

        # load data

        self.SZA.readPixels(0, rownum, self.width, 1, self.sza)
        self.SAZI.readPixels(0, rownum, self.width, 1, self.sazi)
        self.mu0 = np.cos(np.radians(self.sza))
        try:
            self.product.getBand(self.sensordata.cirrus).readPixels(0, rownum, self.width, 1, self.hcld)
        except:
            print("No cirrus band available, high cloud flag discarded")

        # convert (if needed) into TOA reflectance
        if "LANDSAT" in self.sensor:
            self.hcld = self.hcld * np.pi / (self.mu0 * self.U * 366.97)

        for iband in range(self.N):
            # print('loading band '+ str(i))
            # l2h.b[iband].readValidMask(0, y, l2h.width, 1, v)
            # invalid = np.where(v == 0, 1, 0) | invalid
            self.B[iband].readPixels(0, rownum, self.width, 1, self.rs2[iband])
            self.rs2[iband] = np.ma.array(self.rs2[iband], mask=self.rs2[iband] <= 0., fill_value=np.nan)

            self.VZA[iband].readPixels(0, rownum, self.width, 1, self.vza[iband])
            self.VAZI[iband].readPixels(0, rownum, self.width, 1, self.razi[iband])

            # get relative azimuth in OSOAA convention (=0 when sat and sun in opposition)
            self.razi[iband] = 180. - (self.razi[iband] - self.sazi)
            self.razi[iband] = np.array([j % 360 for j in self.razi[iband]])
            self.muv[iband] = np.cos(np.radians(self.vza[iband]))

            # convert (if needed) into TOA reflectance
            if "LANDSAT" in self.sensor:
                self.rs2[iband] = self.rs2[iband] * np.pi / (self.mu0 * self.U * self.solar_irr[iband] * 10)

        # convert into FORTRAN 2D arrays (here, np.array)
        self.rs2 = np.array(self.rs2, order='F').T
        self.razi = np.array(self.razi, order='F').T
        self.vza = np.array(self.vza, order='F').T

    #     print('multiproc')
    #     with closing(Pool(8)) as p:
    #         return(p.map(self.f, range(self.N)))
    #
    # def f(self,iband):
    #     self.B[iband].readPixels(0, 0, self.width, self.height, self.rs2[iband])

    def unload_data(self):

        # unload data
        self.product.getBand('B10').unloadRasterData()
        self.SZA.unloadRasterData()
        self.SAZI.unloadRasterData()

        for i in range(self.N):
            self.B[i].unloadRasterData()
            self.VZA[i].unloadRasterData()
            self.VAZI[i].unloadRasterData()

    def create_product(self):
        from snappy import Product, ProductUtils, ProductIO, ProductData, String

        product = self.product
        ac_product = Product('L2h', 'L2h', self.width, self.height)
        writer = ProductIO.getProductWriter('BEAM-DIMAP')
        ac_product.setProductWriter(writer)
        ProductUtils.copyGeoCoding(product, ac_product)
        ProductUtils.copyMetadata(product, ac_product)
        ac_product.setStartTime(product.getStartTime())
        ac_product.setEndTime(product.getEndTime())

        # add metadata: ancillary data used for processing
        meta = jpy.get_type('org.esa.snap.core.datamodel.MetadataElement')
        att = jpy.get_type('org.esa.snap.core.datamodel.MetadataAttribute')
        # att(name=string,type=int), type: 41L->ascii; 12L->int32;
        att0 = att('AERONET file', ProductData.TYPE_ASCII)
        att0.setDataElems(self.aeronetfile)
        att1 = att('AOT', ProductData.TYPE_ASCII)
        att1.setDataElems(str(self.aot))

        meta = meta('L2')
        meta.setName('Ancillary Data')
        meta.addAttribute(att0)
        meta.addAttribute(att1)
        ac_product.getMetadataRoot().addElement(meta)

        # add data
        # Water-leaving radiance + sunglint
        for iband in range(self.N):
            bname = "Lnw_g_" + self.band_names[iband]
            acband = ac_product.addBand(bname, ProductData.TYPE_FLOAT32)
            acband.setSpectralWavelength(self.wl[iband])
            acband.setSpectralBandwidth(self.B[iband].getSpectralBandwidth())
            acband.setModified(True)
            acband.setNoDataValue(np.nan)
            acband.setNoDataValueUsed(True)
            acband.setValidPixelExpression(bname + ' >= -1')
            ac_product.getBand(bname).setDescription(
                "Water-leaving plus sunglint normalized radiance (Lnw + Lg) in mW cm-2 sr-1 μm-1 at " + self.band_names[
                    iband])

        # Water-leaving radiance
        for iband in range(self.N):
            bname = "Lnw_" + self.band_names[iband]
            acband = ac_product.addBand(bname, ProductData.TYPE_FLOAT32)
            acband.setSpectralWavelength(self.wl[iband])
            acband.setSpectralBandwidth(self.B[iband].getSpectralBandwidth())
            acband.setModified(True)
            acband.setNoDataValue(np.nan)
            acband.setNoDataValueUsed(True)
            acband.setValidPixelExpression(bname + ' >= -1')
            ac_product.getBand(bname).setDescription(
                "Normalized water-leaving radiance in mW cm-2 sr-1 μm-1 at " + self.band_names[iband])

        # Sunglint reflection factor
        # for iband in range(self.N):
        bname = "BRDFg"  # + self.band_names[iband]
        acband = ac_product.addBand(bname, ProductData.TYPE_FLOAT32)
        # acband.setSpectralWavelength(self.wl[iband])
        # acband.setSpectralBandwidth(self.b[iband].getSpectralBandwidth())
        acband.setModified(True)
        acband.setNoDataValue(np.nan)
        acband.setNoDataValueUsed(True)
        acband.setValidPixelExpression(bname + ' >= 0')
        ac_product.getBand(bname).setDescription("Glint reflection factor (BRDF) ")  # + self.band_names[iband])

        # Viewing geometry
        acband = ac_product.addBand("SZA", ProductData.TYPE_FLOAT32)
        acband.setModified(True)
        acband.setNoDataValue(np.nan)
        acband.setNoDataValueUsed(True)
        ac_product.getBand("SZA").setDescription("Solar zenith angle in deg.")

        acband = ac_product.addBand("VZA", ProductData.TYPE_FLOAT32)
        acband.setModified(True)
        acband.setNoDataValue(np.nan)
        acband.setNoDataValueUsed(True)
        ac_product.getBand("VZA").setDescription("Mean viewing zenith angle in deg.")

        acband = ac_product.addBand("AZI", ProductData.TYPE_FLOAT32)
        acband.setModified(True)
        acband.setNoDataValue(np.nan)
        acband.setNoDataValueUsed(True)
        ac_product.getBand("AZI").setDescription("Mean relative azimuth angle in deg.")

        ac_product.setAutoGrouping("Lnw:Lnw_g_")
        ac_product.writeHeader(String(self.outfile + ".dim"))
        self.l2_product = ac_product

    def print_info(self):
        ''' print info, can be used to check if object is complete'''
        print("Product: %s, %d x %d pixels, %s" % (self.name, self.width, self.height, self.description))
        print("Bands:   %s" % (list(self.band_names)))
        for i in range(len(self.wl)):
            print("Band " + str(i) + " at " + str(self.B[i].getSpectralWavelength()) + "nm loaded")


class utils:
    def get_resampled(self, s2_product, resolution=20, method='Bilinear'):
        '''method: Nearest, Bilinear'''
        GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()

        HashMap = jpy.get_type('java.util.HashMap')
        BandDescriptor = jpy.get_type('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor')

        parameters = HashMap()
        parameters.put('targetResolution', resolution)
        parameters.put('upsampling', method)
        parameters.put('downsampling', 'Mean')
        parameters.put('flagDownsampling', 'FlagMedianAnd')
        parameters.put('resampleOnPyramidLevels', True)

        return GPF.createProduct('Resample', parameters, s2_product)

    def get_subset(self, product, wkt):
        '''subset from wkt POLYGON '''
        SubsetOp = jpy.get_type('org.esa.snap.core.gpf.common.SubsetOp')
        WKTReader = jpy.get_type('com.vividsolutions.jts.io.WKTReader')

        grid = WKTReader().read(wkt)
        op = SubsetOp()
        op.setSourceProduct(product)
        op.setGeoRegion(grid)
        return op.getTargetProduct()

    def print_array(self, arr):
        np.set_printoptions(threshold=np.nan)
        print
        arr

    def getMinMax(self, current, minV, maxV):
        if current < minV:
            minV = current
        if current > maxV:
            maxV = current
        return [minV, maxV]

    def get_extent(self, product):
        '''Get corner coordinates of the ESA SNAP product(getextent)
        ########
        # int step - the step given in pixels'''
        step = 1
        lonmin = 999.99

        GeoPos = ProductUtils.createGeoBoundary(product, step)

        lonmax = -lonmin
        latmin = lonmin
        latmax = lonmax

        for element in GeoPos:
            try:
                lon = element.getLon()
                [lonmin, lonmax] = self.getMinMax(lon, lonmin, lonmax)
            except (NameError):
                pass
            try:
                # TODO: separate method to get min and max
                lat = element.getLat()
                [latmin, latmax] = self.getMinMax(lat, latmin, latmax)
            except (NameError):
                pass
        wkt = "POLYGON((" + str(lonmax) + " " + str(latmax) + "," + str(lonmax) + " " \
              + str(latmin) + "," + str(lonmin) + " " + str(latmin) + "," + str(lonmin) + " " \
              + str(latmax) + "," + str(lonmax) + " " + str(latmax) + "))"

        return wkt

    def getReprojected(self, product, crs='EPSG:4326', method='Bilinear'):
        '''Reproject a snappy product on a given coordinate reference system (crs)'''
        from snappy import GPF

        HashMap = jpy.get_type('java.util.HashMap')
        GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()

        parameters = HashMap()
        parameters.put('crs', crs)
        parameters.put('resampling', method)

        return GPF.createProduct('Reproject', parameters, product)
