
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
project_folder = '/DATA/projet/'+project+'/timeseries'
ofile = os.path.join(project_folder,'cloud_cover_timeseries_'+project+'_S2.csv')

time_span = ('2015-03-01', '2019-07-31')
time_span = ('2019-01-01', '2019-08-31')
# karaoun
bbox_coords_wgs84 = [35.62, 33.47, 35.78, 33.67]
# tchad
bbox_coords_wgs84 = [14.221, 12.728, 14.84, 13.287]
latmin, latmax, lonmin, lonmax = 4.65, 5.10, -53.25,-52.85
bbox_coords_wgs84 = [lonmin,latmin, lonmax,  latmax]

bbox = BBox(bbox_coords_wgs84, crs=CRS.WGS84)

data_folder = os.path.join(project_folder,'data')

LAYER_NAME = 'TRUE-COLOR-S2-L1C'


cmap = cm.cm.thermal #tools.crop_by_percent(cm.cm.delta, 30, which='both')


fig_preview = os.path.join('fig','preview_'+time_span[0]+'_'+time_span[1]+'.pdf')
fig_proba = os.path.join('fig','cloud_proba_'+time_span[0]+'_'+time_span[1]+'.pdf')

ts = timeseries(project_folder, bbox, time_span, instance_id=INSTANCE_ID)
ts.get_previews()
#ts.plot_preview(filename=fig_preview)

ts.get_custom()#redownload=True)

cloud_detector = S2PixelCloudDetector(threshold=0.4, average_over=4, dilation_size=2)

ts.cloud_probs = cloud_detector.get_cloud_probability_maps(ts.custom_bands)
ts.cloud_masks = cloud_detector.get_cloud_masks(ts.custom_bands)
ts.get_coverage()

ts._plot_image(ts.cloud_probs,cmap=cmap,ctitle='Cloud probability (0 --> no cloud)', filename=fig_proba)
ts.overlay_cloud_mask(ts.previews,ts.cloud_masks, filename=fig_preview)

cc_df = pd.DataFrame(index=ts.dates,data={'cloud_cover': ts.cloud_coverage })
cc_df.to_csv(ofile)
plt.Figure(figsize=(20,5))
p = cc_df.plot(marker='o', linestyle='-')
p.s

plt.plot(all_cloud_masks.get_dates(),cc.mean(axis=(1,2)))

#####################
# END
#####################
