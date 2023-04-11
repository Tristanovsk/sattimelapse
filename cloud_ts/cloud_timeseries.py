import os

import datetime
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import cmocean as cm

from sentinelhub import WmsRequest, BBox, CRS, MimeType, CustomUrlParam, get_area_dates
from s2cloudless import S2PixelCloudDetector, CloudMaskRequest

from cloud_ts.sentinelhub_ts import timeseries

with open('myID.txt') as f:
    INSTANCE_ID = f.readline()

project = "petit-saut"
project_folder = '/DATA/projet/' + project + '/timeseries'
ofile = os.path.join(project_folder, 'cloud_cover_timeseries_' + project + '_S2.csv')
latmin, latmax, lonmin, lonmax = 4.65, 5.10, -53.25, -52.85
# karaoun
# project = "Karaoun"
# project_folder = '/DATA/projet/'+project+'/timeseries'
# ofile = os.path.join(project_folder,'cloud_cover_timeseries_'+project+'_S2.csv')
# bbox_coords_wgs84 = [35.62, 33.47, 35.78, 33.67]

# tchad
lonmin, latmin, lonmax, latmax = 14.221, 12.728, 14.84, 13.287
project_folder = '/DATA/projet/unesco/timeseries'
project = "lake_chad"

# manaus
lonmin, latmin, lonmax, latmax = -60.1, -3.265, -59.7, -3.02
project_folder = '/DATA/projet/hydrosim/timeseries'
project = "manaus"

time_span = ('2015-03-01', '2020-02-27')
# time_span = ('2019-11-01', '2020-02-27')

ofile = os.path.join(project_folder,
                     'cloud_cover_timeseries_' + time_span[0] + 'to' + time_span[1] + '_' + project + '_S2')

bbox_coords_wgs84 = [lonmin, latmin, lonmax, latmax]
bbox = BBox(bbox_coords_wgs84, crs=CRS.WGS84)

data_folder = os.path.join(project_folder, 'data')

LAYER_NAME = 'TRUE-COLOR-S2-L1C'

cmap = cm.cm.thermal  # tools.crop_by_percent(cm.cm.delta, 30, which='both')

fig_preview = os.path.join('fig', 'preview_' + time_span[0] + '_' + time_span[1] + '.pdf')
fig_proba = os.path.join('fig', 'cloud_proba_' + time_span[0] + '_' + time_span[1] + '.pdf')

ts = timeseries(project_folder, bbox, time_span, instance_id=INSTANCE_ID)
ts.get_previews()

print('mask invalid images')
ts.mask_invalid_images(max_invalid_coverage=0.01)


# get full data
ts.get_custom()  # redownload=True)

# filter out inconsistent images
ts.dates = ts.dates[ts.mask == 0]
ts.previews = ts.previews[ts.mask == 0]
ts.custom_bands = ts.custom_bands[ts.mask == 0]
ts.mask = ts.mask[ts.mask == 0]

cloud_detector = S2PixelCloudDetector(threshold=0.4, average_over=4, dilation_size=2)
try:
    ts._load_cloud_probs()
except:
    print('compute cloud probability')
    ts.cloud_probs = cloud_detector.get_cloud_probability_maps(ts.custom_bands)
    ts._save_cloud_probs()

try:
    ts._load_cloud_masks()
except:
    print('set cloud mask')
    ts.cloud_masks = cloud_detector.get_cloud_masks(ts.custom_bands)
    ts._save_cloud_masks()

ts.get_coverage()
# plot low-res images
ts.plot_preview(filename=fig_preview)
ts.get_fullres()
ts.plot_fullres()



ts._plot_image(ts.cloud_probs, cmap=cmap, ctitle='Cloud probability (0 --> no cloud)', filename=fig_proba)
ts.overlay_cloud_mask(ts.previews, ts.cloud_masks, filename=fig_preview)

cc_df = pd.DataFrame(index=ts.dates, data={'cloud_cover': ts.cloud_coverage})
cc_df.to_csv(ofile + '.csv')
fig, ax = plt.subplots(1, 1, figsize=(20, 5))
p = cc_df.plot(ax=ax, marker='o', linestyle='-')
ax.set_ylabel('Cloud Cover (0: clear, 1: overcast)')
plt.savefig(ofile + '.png', bbox_inches='tight')

# --------------------------------
# make video of cloud free images
# --------------------------------
max_cc = 0.09
scale_factor = .43
fps = 3
# to mnually mask images by index
mask_images = []
ts.mask_cloudy_images(max_cloud_coverage=max_cc)
ts.mask_images(mask_images)
ts.create_date_stamps()
ts.create_timelapse(scale_factor=scale_factor)
ts.make_video_alternate(fps=fps)

#####################
# END
#####################
