
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


project_folder = '/DATA/projet/unesco/timeseries'

time_span = ('2015-03-01', '2019-07-31')
time_span = ('2019-01-01', '2019-07-31')
# karaoun
bbox_coords_wgs84 = [35.62, 33.47, 35.78, 33.67]
# tchad
bbox_coords_wgs84 = [14.221, 12.728, 14.84, 13.287]
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
cc_df.to_csv('/DATA/projet/Karaoun/cloud_cover_timeseries_Karaoun_S2.csv')
plt.Figure(figsize=(20,5))
p = cc_df.plot(marker='o', linestyle='-')
p.s
plt.plot(all_cloud_masks.get_dates(),cc.mean(axis=(1,2)))

#####################
# END
#####################

wms_true_color_request = WmsRequest(data_folder=data_folder,layer=LAYER_NAME,
                                    bbox=bounding_box,
                                    time=time_span,
                                    width=600, height=None,
                                    image_format=MimeType.PNG,
                                    instance_id=INSTANCE_ID)

obj = u.plot()
obj.previews = np.asarray(wms_true_color_request.get_data(save_data=True, redownload=False))
obj.dates = wms_true_color_request.get_dates()
obj.plot_previews(filename=fig_preview)

bands_script = 'return [B01,B02,B04,B05,B08,B8A,B09,B10,B11,B12]'
wms_bands_request = WmsRequest(data_folder=data_folder,
                               layer=LAYER_NAME,
                               custom_url_params={
                                   CustomUrlParam.EVALSCRIPT: bands_script,
                                   CustomUrlParam.ATMFILTER: 'NONE'
                               },
                               bbox=bounding_box,
                               time=time_span,
                               width=600, height=None,
                               image_format=MimeType.TIFF_d32f,
                               instance_id=INSTANCE_ID)
# ----------------------
# actual download
# ----------------------
wms_bands = wms_bands_request.get_data(save_data=True, redownload=False)


cloud_detector = S2PixelCloudDetector(threshold=0.4, average_over=4, dilation_size=2)

cloud_probs = cloud_detector.get_cloud_probability_maps(np.array(wms_bands))
cloud_masks = cloud_detector.get_cloud_masks(np.array(wms_bands))

image_idx = 0
u.plot.overlay_cloud_mask(wms_true_color_imgs[image_idx], cloud_masks[image_idx])
u.plot.plot_probability_map(wms_true_color_imgs[image_idx], cloud_probs[image_idx])

all_cloud_masks = CloudMaskRequest(ogc_request=wms_bands_request, threshold=0.1)
fig = plt.figure(figsize=(15, 10))
n_cols = 4
n_rows = int(np.ceil(len(wms_true_color_imgs) / n_cols))

for idx, [prob, mask, data] in enumerate(all_cloud_masks):
    ax = fig.add_subplot(n_rows, n_cols, idx + 1)
    image = wms_true_color_imgs[idx]
    u.plot.overlay_cloud_mask(image, mask, factor=1, fig=fig)

plt.tight_layout()
plt.savefig('cc_ts_karaoun.pdf')
plt.close()

cc = all_cloud_masks.get_cloud_masks()

ts = pd.DataFrame(index=all_cloud_masks.get_dates(),data={'pb': cc.mean(axis=(1,2)) })

plt.plot(all_cloud_masks.get_dates(),cc.mean(axis=(1,2)))