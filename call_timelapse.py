import os, sys
import geopandas as gpd

from sentinelhub.common import BBox, CRS
from sattimelapse.time_lapse import SentinelHubTimelapse

# Loading polygon of nominal water extent
from shapely.wkt import loads

WMS_INSTANCE = '31d7cfd1-64ac-409c-a027-0a2ec537aa95'


# wkt_file = 'theewaterskloof_dam_nominal.wkt'

def bbox_creator(wkt_file, inflate_bbox=0.5, minsize=[0.025, 0.015]):
    with open(wkt_file, 'r') as f:
        wkt = f.read()

    nominal = loads(wkt)

    # inflate the BBOX
    minx, miny, maxx, maxy = nominal.bounds
    delx = maxx - minx
    dely = maxy - miny

    # set minimal frame size
    delx = max(delx * inflate_bbox, minsize[0])
    dely = max(dely * inflate_bbox, minsize[1])

    minx = minx - delx
    maxx = maxx + delx
    miny = miny - dely
    maxy = maxy + dely

    return BBox(bbox=[minx, miny, maxx, maxy], crs=CRS.WGS84)


def get_bbox_size(bbox):
    from geographiclib.geodesic import Geodesic

    geod = Geodesic.WGS84
    b = bbox.get_polygon()
    p1_lat, p1_lon = b[0][0], b[0][1]
    p2_lat, p2_lon = b[1][0], b[1][1]
    p3_lat, p3_lon = b[2][0], b[2][1]

    gx = geod.Inverse(p1_lat, p1_lon, p2_lat, p2_lon)
    gy = geod.Inverse(p2_lat, p2_lon, p3_lat, p3_lon)
    print("Distance is E-W x N-S {:.2f}m x {:.2f}m".format(gx['s12'], gy['s12']))
    return gx['s12'], gy['s12']


time_interval = ['2015-05-01', '2018-09-30']


def make_timelapse(msg, bbox, time_interval, *, mask_images=[], new=True, clean=False,
                   max_cc=0.33, scale_factor=.43, fps=3, instance_id=WMS_INSTANCE, **kwargs):
    global timelapse
    timelapse = SentinelHubTimelapse(msg, bbox, time_interval, new, clean, instance_id, **kwargs)
    if new:
        timelapse.get_previews()
        timelapse.save_fullres_images()
        timelapse.plot_preview(filename='previews.pdf')
        timelapse.mask_invalid_images(max_invalid_coverage=0.01)
        timelapse.mask_cloudy_images(max_cloud_coverage=max_cc)
        timelapse.plot_cloud_masks(filename='cloudmasks.pdf')
        timelapse.plot_fullres(filename='previews_with_cc.pdf')
        timelapse.mask_images(mask_images)
        timelapse.create_date_stamps()
        timelapse.create_timelapse(scale_factor=scale_factor)

    timelapse.make_video_alternate(fps=fps)


def shp2wkt(shapefile):
    tmp = gpd.GeoDataFrame.from_file(shapefile)
    tmp.to_crs(epsg=4326, inplace=True)
    wkt = tmp.geometry.values[0].to_wkt()

    with open(shapefile.replace('shp', 'wkt'), "w") as text_file:
        text_file.write(wkt)


lake = 'RAV34'

idir = sys.argv[1]
lake = sys.argv[2]

project_name = os.path.join(idir, lake)
wkt_file = os.path.join(project_name, 'shape', lake + '.wkt')
if not os.path.isfile(wkt_file):
    shp2wkt(wkt_file.replace('wkt', 'shp'))
bbox = bbox_creator(wkt_file, 0.3)
x,y = get_bbox_size(bbox)
small_area = True
if (x >= 50000) | (y >= 50000):
    small_area = False

make_timelapse(project_name, bbox, time_interval, new=True, clean=False,small_area=small_area)

#
# from time_lapse import SentinelHubTimelapse
#
# project_name = "/DATA/OBS2CO/water_surface_monitoring/NAU48"
# timelapse = SentinelHubTimelapse(project_name)
# timelapse.make_video_alterbate()
