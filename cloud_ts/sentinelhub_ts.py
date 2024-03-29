"""
Module docstring.
"""

import datetime
import logging

import os
import glob

from dateutil.rrule import rrule, MONTHLY

from itertools import compress

import cv2
import imageio
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

from sentinelhub.data_request import WmsRequest, WcsRequest
from sentinelhub.constants import MimeType, CustomUrlParam
from s2cloudless import CloudMaskRequest, MODEL_EVALSCRIPT

appdir = os.path.dirname(os.path.abspath(__file__))
datestamps_dir = os.path.join(appdir, 'datestamps')

LOGGER = logging.getLogger(__name__)


class timeseries(object):
    """
    Class for creating timeseries with satellite images available through SentinelHub portal
    """

    def __init__(self, project_name, bbox=None, time_interval=None, new=True, clean=False, instance_id='',
                 full_res=('10m', '10m'), preview_res=('60m', '60m'), cloud_mask_res=('60m', '60m'),
                 full_size=(1920, 1080), preview_size=(600, None),
                 use_atmcor=False, layer='TRUE-COLOR-S2-L1C',
                 custom_script='return [B01,B02,B04,B05,B08,B8A,B09,B10,B11,B12]',
                 time_difference=datetime.timedelta(hours=2), pix_based=False):

        self.project_name = project_name
        self.preview_folder = os.path.join(project_name, 'data', 'previews')
        self.data_folder = os.path.join(project_name, 'data', 'full_res')
        self.mask_folder = os.path.join(project_name, 'data', 'custom')
        self.cloud_masks = None
        self.cloud_coverage = None
        self.full_res_data = None
        self.previews = None
        self.full_res = full_res
        self.timelapse = None

        if clean:
            self.clean_all()

        if not new:
            return

        if pix_based:
            self.preview_request = WcsRequest(data_folder=self.preview_folder, layer=layer, bbox=bbox,
                                              time=time_interval, resx=preview_res[0], resy=preview_res[1],
                                              maxcc=1.0, image_format=MimeType.PNG, instance_id=instance_id,
                                              custom_url_params={CustomUrlParam.TRANSPARENT: True},
                                              time_difference=time_difference)

            self.fullres_request = WcsRequest(data_folder=self.data_folder, layer=layer, bbox=bbox,
                                              time=time_interval, resx=full_res[0], resy=full_res[1],
                                              maxcc=1.0, image_format=MimeType.PNG, instance_id=instance_id,
                                              custom_url_params={CustomUrlParam.TRANSPARENT: True,
                                                                 CustomUrlParam.ATMFILTER: 'ATMCOR'} if use_atmcor else {
                                                  CustomUrlParam.TRANSPARENT: True},
                                              time_difference=time_difference)
            self.custom_request = WcsRequest(data_folder=self.mask_folder, layer=layer, bbox=bbox, time=time_interval,
                                             resx=cloud_mask_res[0], resy=cloud_mask_res[1], maxcc=1.0,
                                             image_format=MimeType.TIFF_d32f, instance_id=instance_id,
                                             time_difference=time_difference,
                                             custom_url_params={CustomUrlParam.EVALSCRIPT: custom_script,
                                                                CustomUrlParam.ATMFILTER: 'NONE'})
        else:
            self.preview_request = WmsRequest(data_folder=self.preview_folder, layer=layer, bbox=bbox,
                                              time=time_interval, width=preview_size[0], height=preview_size[1],
                                              maxcc=1.0, image_format=MimeType.PNG, instance_id=instance_id,
                                              custom_url_params={CustomUrlParam.TRANSPARENT: True},
                                              time_difference=time_difference)

            self.fullres_request = WmsRequest(data_folder=self.data_folder, layer=layer, bbox=bbox,
                                              time=time_interval, width=full_size[0], height=full_size[1],
                                              maxcc=1.0, image_format=MimeType.PNG, instance_id=instance_id,
                                              custom_url_params={CustomUrlParam.TRANSPARENT: True,
                                                                 CustomUrlParam.ATMFILTER: 'ATMCOR'} if use_atmcor else {
                                                  CustomUrlParam.TRANSPARENT: True},
                                              time_difference=time_difference)

            self.custom_request = WmsRequest(data_folder=self.mask_folder, layer=layer, bbox=bbox, time=time_interval,
                                             width=preview_size[0], height=preview_size[1], maxcc=1.0,
                                             image_format=MimeType.TIFF_d32f, instance_id=instance_id,
                                             time_difference=time_difference,
                                             custom_url_params={CustomUrlParam.EVALSCRIPT: custom_script,
                                                                CustomUrlParam.ATMFILTER: 'NONE'})

        self.cloud_mask_request = None  # CloudMaskRequest(wcs_request)

        self.transparency_data = None
        self.preview_transparency_data = None
        self.invalid_coverage = None

        self.dates = self.preview_request.get_dates()

        if not self.dates:
            raise ValueError('Input parameters are not valid. No Sentinel 2 image is found.')

        if self.dates != self.fullres_request.get_dates():
            raise ValueError('Lists of previews and full resolution images do not match.')

        # if self.dates != self.cloud_mask_request.get_dates():
        #     raise ValueError('List of previews and cloud masks do not match.')
        self.dates = np.array(self.dates)
        self.mask = np.zeros((len(self.dates),), dtype=np.uint8)

        LOGGER.info('Found %d images of %s between %s and %s.', len(self.dates), project_name,
                    time_interval[0], time_interval[1])

        LOGGER.info('\nI suggest you start by downloading previews first to see,\n'
                    'if BBOX is OK, images are usefull, etc...\n'
                    'Execute get_previews() method on your object.\n')

    def clean_data(self):
        CommonUtil.clean_folder(self.data_folder)

    def clean_preview(self):
        CommonUtil.clean_folder(self.preview_folder)

    def clean_all(self):
        self.clean_preview()
        self.clean_data()

    def get_previews(self, save_data=True, redownload=False):
        """
        Downloads and returns an numpy array of previews if previews were not already downloaded and saved to disk.
        Set `redownload` to True if to force downloading the previews again.
        """

        self.previews = np.asarray(self.preview_request.get_data(save_data=save_data, redownload=redownload))
        self.preview_transparency_data = self.previews[:, :, :, -1]

        LOGGER.info('%d previews have been downloaded and stored to numpy array of shape %s.', self.previews.shape[0],
                    self.previews.shape)

    def get_fullres(self, save_data=True, redownload=False):
        """
        Downloads and saves fullres images used to produce the timelapse. Note that images for all available dates
        within the specified time interval are downloaded, although they will be for example masked due to too high
        cloud coverage.
        """

        data4d = np.asarray(self.fullres_request.get_data(save_data=save_data, redownload=redownload))
        self.full_res_data = data4d[:, :, :, :-1]
        self.transparency_data = data4d[:, :, :, -1]

    def get_custom(self, save_data=True, redownload=False):
        """
        Downloads and saves custom-band images
        """

        self.custom_dates = self.custom_request.get_dates()
        self.custom_bands = np.asarray(self.custom_request.get_data(save_data=save_data, redownload=redownload))
        LOGGER.info('%d tiff data have been downloaded and stored to numpy array of shape %s.', self.custom_bands.shape[0],
                    self.custom_bands.shape)

    def overlay_cloud_mask(self, rgb_img, mask, within_range=None, filename=None):
        """
        Utility function for plotting RGB images with binary mask overlayed.
        """
        within_range = CommonUtil.get_within_range(within_range, rgb_img.shape[0])
        self._plot_image(rgb_img[within_range[0]: within_range[1]],
                         factor=1, mask=mask, filename=filename)

    def plot_preview(self, within_range=None, filename=None):
        """
        Plots all previews if within_range is None, or only previews in a given range.
        """
        within_range = CommonUtil.get_within_range(within_range, self.previews.shape[0])
        self._plot_image(self.previews[within_range[0]: within_range[1]] / 255., factor=1, filename=filename)

    def plot_fullres(self, within_range=None, filename=None):
        """
        Plots all previews if within_range is None, or only previews in a given range.
        """
        within_range = CommonUtil.get_within_range(within_range, self.full_res_data.shape[0])
        self._plot_image(self.full_res_data[within_range[0]: within_range[1]] / 255., factor=1, filename=filename)

    def plot_cloud_masks(self, within_range=None, filename=None):
        """
        Plots all cloud masks if within_range is None, or only masks in a given range.
        """
        within_range = CommonUtil.get_within_range(within_range, self.cloud_masks.shape[0])
        self._plot_image(self.cloud_masks[within_range[0]: within_range[1]],
                         factor=1, cmap=plt.cm.binary, filename=filename)

    def _plot_image(self, data, factor=2.5, cmap=None, ctitle='', mask=None, filename=None):

        rows = data.shape[0] // 5 + (1 if data.shape[0] % 5 else 0)
        aspect_ratio = (1.0 * data.shape[1]) / data.shape[2]
        fig, axs = plt.subplots(nrows=rows, ncols=5, figsize=(15, 3 * rows * aspect_ratio))
        for index, ax in enumerate(axs.flatten()):
            if index < data.shape[0] and index < len(self.dates):
                caption = str(index) + ': ' + self.dates[index].strftime('%Y-%m-%d')
                if self.cloud_coverage is not None:
                    caption = caption + '(' + "{0:2.0f}".format(self.cloud_coverage[index] * 100.0) + '%)'

                ax.set_axis_off()
                im = ax.imshow(data[index] * factor if data[index].shape[-1] == 3 or data[index].shape[-1] == 4 else
                               data[index] * factor, cmap=cmap, vmin=0.0, vmax=1.0)
                if mask is not None:
                    mask_ = mask[index]
                    cloud_image = np.zeros((mask_.shape[0], mask_.shape[1], 4), dtype=np.uint8)
                    cloud_image[mask_ == 1] = np.asarray([255, 255, 0, 100], dtype=np.uint8)
                    ax.imshow(cloud_image)
                ax.text(0, -2, caption, fontsize=12, color='r' if self.mask[index] else 'g')
            else:
                ax.set_axis_off()

        if cmap is not None:
            cax = fig.add_axes([0.35, 0.97, 0.3, 0.015])
            cbar = plt.colorbar(im, cax, orientation='horizontal')
            cbar.set_label(ctitle)
        if filename:
            plt.savefig(self.project_name + '/' + filename, bbox_inches='tight')
            plt.close()

    def _load_cloud_masks(self):
        """
        Loads masks from disk, if they already exist.
        """
        cloud_masks_filename = self.project_name + '/cloudmasks/cloudmasks.npy'

        if not os.path.isfile(cloud_masks_filename):
            return False

        with open(cloud_masks_filename, 'rb') as fp:
            self.cloud_masks = np.load(fp)
        return True

    def _save_cloud_masks(self):
        """
        Saves masks to disk.
        """
        cloud_masks_filename = self.project_name + '/cloudmasks/cloudmasks.npy'

        if not os.path.exists(self.project_name + '/cloudmasks'):
            os.makedirs(self.project_name + '/cloudmasks')

        with open(cloud_masks_filename, 'wb') as fp:
            np.save(fp, self.cloud_masks)

    def _load_cloud_probs(self):
        """
        Loads masks from disk, if they already exist.
        """
        cloud_probs_filename = self.project_name + '/cloudmasks/cloudprobs.npy'

        if not os.path.isfile(cloud_probs_filename):
            return False

        with open(cloud_probs_filename, 'rb') as fp:
            self.cloud_probs = np.load(fp)
        return True

    def _save_cloud_probs(self):
        """
        Saves masks to disk.
        """
        cloud_probs_filename = self.project_name + '/cloudmasks/cloudprobs.npy'

        if not os.path.exists(self.project_name + '/cloudmasks'):
            os.makedirs(self.project_name + '/cloudmasks')

        with open(cloud_probs_filename, 'wb') as fp:
            np.save(fp, self.cloud_probs)

    def _run_cloud_detection(self, rerun, threshold):
        """
        Determines cloud masks for each acquisition.
        """
        loaded = self._load_cloud_masks()
        if loaded and not rerun:
            LOGGER.info('Nothing to do. Masks are loaded.')
        else:
            LOGGER.info('Downloading cloud data and running cloud detection. This may take a while.')
            self.cloud_masks = self.cloud_mask_request.get_cloud_masks(threshold=threshold)
            self._save_cloud_masks()

    def mask_cloudy_images(self, rerun=False, max_cloud_coverage=0.1, threshold=None):
        """
        Marks images whose cloud coverage exceeds ``max_cloud_coverage``. Those
        won't be used in timelapse.

        :param rerun: Whether to rerun cloud detector
        :type rerun: bool
        :param max_cloud_coverage: Limit on the cloud coverage of images forming timelapse, 0 <= maxcc <= 1.
        :type max_cloud_coverage: float
        :param threshold:  A float from [0,1] specifying cloud threshold
        :type threshold: float or None
        """
        if not rerun:
            self._run_cloud_detection(rerun, threshold)

        self.cloud_coverage = np.asarray([self._get_coverage(mask) for mask in self.cloud_masks])

        for index in range(0, len(self.mask)):
            if self.cloud_coverage[index] > max_cloud_coverage:
                self.mask[index] = 1

    def mask_invalid_images(self, max_invalid_coverage=0.1):
        """
        Marks images whose invalid area coverage exceeds ``max_invalid_coverage``. Those
        won't be used in timelapse.

        :param max_invalid_coverage: Limit on the invalid area coverage of images forming timelapse, 0 <= maxic <= 1.
        :type max_invalid_coverage: float
        """

        # low-res and hi-res images/cloud masks may differ, just to be safe
        # but here masking is done on previews
        #coverage_fullres = np.asarray([1.0 - self._get_coverage(mask) for mask in self.transparency_data])
        coverage_preview = np.asarray([1.0 - self._get_coverage(mask) for mask in self.preview_transparency_data])
        #self.invalid_coverage = np.array([max(x, y) for x, y in zip(coverage_fullres, coverage_preview)])

        self.invalid_coverage = coverage_preview

        for index in range(0, len(self.mask)):
            if self.invalid_coverage[index] > max_invalid_coverage:
                self.mask[index] = 1

    def mask_images(self, idx):
        """
        Manually mask images with given indexes.
        """
        for index in idx:
            self.mask[index] = 1

    def unmask_images(self, idx):
        """
        Manually unmask images with given indexes.
        """
        for index in idx:
            self.mask[index] = 0

    def create_date_stamps(self):
        """
        Create date stamps to be included to gif.
        """
        filtered = list(compress(self.dates, list(np.logical_not(self.mask))))

        if not os.path.exists(datestamps_dir):
            os.makedirs(datestamps_dir)

        for date in filtered:
            datefile = os.path.join(datestamps_dir, date.strftime("%Y-%m-%d") + '.png')
            if not os.path.isfile(datefile):
                TimestampUtil.create_date_stamp(date, filtered[0], filtered[-1], datefile)

    def create_timelapse(self, scale_factor=0.3):
        """
        Adds date stamps to full res images and stores them in timelapse subdirectory.
        """
        filtered = list(compress(self.dates, list(np.logical_not(self.mask))))

        if not os.path.exists(self.project_name + '/timelapse'):
            os.makedirs(self.project_name + '/timelapse')

        self.timelapse = [
            TimestampUtil.add_date_stamp(self._get_filename(self.data_folder, date.strftime("%Y-%m-%dT%H-%M-%S")),
                                         self.project_name + '/timelapse/' + date.strftime(
                                             "%Y-%m-%dT%H-%M-%S") + '.png',
                                         self._get_filename(datestamps_dir, date.strftime("%Y-%m-%d")),
                                         scale_factor=scale_factor) for date in filtered]

    def get_coverage(self, cloud_masks=None):
        if cloud_masks is None:
            cloud_masks = self.cloud_masks
        self.cloud_coverage = np.asarray([self._get_coverage(mask) for mask in cloud_masks])

    @staticmethod
    def _get_coverage(mask):
        coverage_pixels = np.count_nonzero(mask)
        return 1.0 * coverage_pixels / mask.size

    @staticmethod
    def _iso_to_datetime(date):
        """ Convert ISO 8601 time format to datetime format

        This function converts a date in ISO format, e.g. 2017-09-14 to a datetime instance, e.g.
        datetime.datetime(2017,9,14,0,0)

        :param date: date in ISO 8601 format
        :type date: str
        :return: datetime instance
        :rtype: datetime
        """
        chunks = list(map(int, date.split('T')[0].split('-')))
        return datetime(chunks[0], chunks[1], chunks[2])

    @staticmethod
    def _datetime_to_iso(date, only_date=True):
        """ Convert datetime format to ISO 8601 time format

        This function converts a date in datetime instance, e.g. datetime.datetime(2017,9,14,0,0) to ISO format,
        e.g. 2017-09-14

        :param date: datetime instance to convert
        :type date: datetime
        :param only_date: whether to return date only or also time information. Default is `True`
        :type only_date: bool
        :return: date in ISO 8601 format
        :rtype: str
        """
        if only_date:
            return date.isoformat().split('T')[0]
        return date.isoformat()

    @staticmethod
    def _diff_month(start_dt, end_dt):
        return (end_dt.year - start_dt.year) * 12 + end_dt.month - start_dt.month + 1

    @staticmethod
    def _get_month_list(start_dt, end_dt):
        month_names = {1: 'J', 2: 'F', 3: 'M', 4: 'A', 5: 'M', 6: 'J', 7: 'J', 8: 'A', 9: 'S', 10: 'O', 11: 'N',
                       12: 'D'}

        total_months = timeseries._diff_month(start_dt, end_dt)
        all_months = list(rrule(MONTHLY, count=total_months, dtstart=start_dt))
        return [month_names[date.month] for date in all_months]

    def _get_filename(self, dir, date):
        for filename in glob.glob(dir + '/*'):
            if date in filename:
                return filename
        return None

    def _get_timelapse_files(self, subdir='timelapse'):
        return sorted(glob.glob(self.project_name + '/' + subdir + '/*png'))

    def _get_timelapse_images(self):
        if self.timelapse is None:
            data = np.array(self.fullres_request.get_data())[:, :, :, :-1]
            return [data[idx] for idx, _ in enumerate(data) if self.mask[idx] == 0]
        return self.timelapse

    def make_video(self, filename='timelapse.mp4', fps=2, is_color=True, n_repeat=0):
        """
        Creates and saves an AVI video from timelapse into ``timelapse.avi``
        :param fps: frames per second
        :type param: int
        :param is_color:
        :type is_color: bool
        """

        images = np.array([image[:, :, [2, 1, 0]] for image in self._get_timelapse_images()])
        self.full_size = (int(images.shape[2]), int(images.shape[1]))

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video = cv2.VideoWriter(os.path.join(self.project_name, filename), fourcc, float(fps), self.full_size,
                                is_color)

        for _ in range(n_repeat):
            for image in images:
                video.write(image)
        video.write(images[-1])

        video.release()

    def make_video_alternate(self, video_name='timelapse.mp4', fps=3, is_color=True, n_repeat=0):
        """
        Creates and saves an AVI video from timelapse into ``timelapse.avi``
        :param fps: frames per second
        :type param: int
        :param is_color:
        :type is_color: bool
        """
        video_fullname = os.path.join(self.project_name, video_name)

        images = self._get_timelapse_files()  # [img for img in os.listdir(image_folder) if img.endswith(".png")]
        frame = cv2.imread(images[0])
        height, width, layers = frame.shape
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video = cv2.VideoWriter(video_fullname, fourcc, fps, (width, height))

        for image in images:
            video.write(cv2.imread(image))

        # cv2.destroyAllWindows()
        video.release()

    def make_gif(self, filename='timelapse.gif', fps=3, loop=0):
        """
        Creates and saves a GIF animation from timelapse into ``timelapse.gif``
        :param fps: frames per second
        :type fps: int
        """
        with imageio.get_writer(os.path.join(self.project_name, filename), mode='I', fps=fps) as writer:
            for filename in self._get_timelapse_files():
                image = imageio.imread(filename)
                writer.append_data(image)


class TimestampUtil:
    """
    Utility methods related to timestamps.
    """

    @staticmethod
    def add_date_stamp(input_image_path, output_image_path, watermark_image_path,
                       scale_factor=0.3, minsize=1000):

        base_image = Image.open(input_image_path)
        w, h = base_image.size
        if w < minsize:
            scale = minsize / w
            base_image = base_image.resize((int(scale * w), int(scale * h)), Image.ANTIALIAS)

        watermark = Image.open(watermark_image_path)

        width, height = base_image.size
        w_width, w_height = watermark.size

        scale = scale_factor * width / w_width

        watermark = watermark.resize((int(scale * w_width), int(scale * w_height)), Image.ANTIALIAS)

        transparent = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        transparent.paste(base_image, (0, 0))
        transparent.paste(watermark, (width - int(scale * w_width), 0), mask=watermark)
        transparent.save(output_image_path)
        # Convert RGBA to RGB and return as numpy
        return np.array(transparent.convert('RGB').getdata()).reshape(height, width, 3).astype(np.uint8)

    @staticmethod
    def create_date_stamp(current_dt, start_dt, end_dt, filename):
        years = TimestampUtil._get_years_in_range(start_dt, end_dt)
        equal_year_size = [1] * len(years)

        months_size = [1] * 12

        # Create colors
        sh_colors = {'light': (255. / 255., 128. / 255, 1. / 255), 'dark': (204. / 255, 110. / 255, 15. / 255)}

        year_colors = [sh_colors['light'] if year <= current_dt.year else sh_colors['dark'] for year in years]
        month_colors = [sh_colors['light'] if index <= current_dt.month else sh_colors['dark'] for index in
                        range(1, 13)]

        # First Ring (outside)
        fig, ax = plt.subplots(figsize=(12.5, 5))
        ax.axis('equal')
        my_pie, texts = ax.pie(equal_year_size, radius=1.5, colors=year_colors,
                               labeldistance=1.05, counterclock=False, startangle=90,
                               textprops={'color': sh_colors['light'], 'weight': 'medium'})

        plt.setp(my_pie, width=0.3, edgecolor=None)

        # Second Ring (Inside)
        my_pie2, texts = ax.pie(months_size, radius=1.5 - 0.3, colors=month_colors,
                                labeldistance=0.9, counterclock=False, startangle=90)

        plt.setp(my_pie2, width=0.4, edgecolor=None)

        if current_dt.day > 9:
            ax.text(-0.6, -0.3, str(current_dt.day), fontsize=100, color=sh_colors['light'], weight='medium')
        else:
            ax.text(-0.3, -0.3, str(current_dt.day), fontsize=100, color=sh_colors['light'], weight='medium')

        ax.text(1.3, 0.8, str(current_dt.year), fontsize=100, color=sh_colors['light'], weight='medium')
        ax.text(2., -0.3, current_dt.strftime('%b'), fontsize=100, color=sh_colors['light'], weight='medium')

        fig.savefig(filename, transparent=True, dpi=300, )
        plt.close()

    @staticmethod
    def _get_years_in_range(start_dt, end_dt):
        return list(range(start_dt.year, end_dt.year + 1))


class CommonUtil:
    @staticmethod
    def get_within_range(within_range, n_imgs):
        """
        Returns the range of images to be plotted.

        :param within_range: tuple of the first and the last image to be plotted, or None
        :type within_range: tuple of ints or None
        :param n_imgs: total number of images
        :type n_imgs: int
        :return: tuple of the first and the last image to be plotted
        :rtype: tuple of two ints
        """
        if within_range is None:
            return [0, n_imgs]
        return max(within_range[0], 0), min(within_range[1], n_imgs)

    @staticmethod
    def clean_folder(path):
        """ empty directory content"""
        for root, dirs, files in os.walk(path):
            for file in files:
                os.remove(os.path.join(root, file))
