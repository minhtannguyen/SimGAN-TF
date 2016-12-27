import os
import sys
import fnmatch
import tarfile
from tqdm import tqdm
from six.moves import urllib

import numpy as np

from utils import loadmat, imwrite

MPIIGAZE_PATH = 'MPIIGaze'
UNITYEYE_PATH = 'UnityEye'

DATA_FNAME = 'gaze.npz'

def maybe_download_and_extract(
    data_path,
    url='http://datasets.d2.mpi-inf.mpg.de/MPIIGAZE_PATH/MPIIGAZE_PATH.tar.gz'):
  if not os.path.exists(os.path.join(data_path, 'MPIIGAZE_PATH')):
    if not os.path.exists(data_path):
      os.makedirs(data_path)

    filename = os.path.basename(url)
    filepath = os.path.join(data_path, filename)

    if not os.path.exists(filepath):
      def _progress(count, block_size, total_size):
        sys.stdout.write('\r>> Downloading %s %.1f%%' % (filename,
          float(count * block_size) / float(total_size) * 100.0))
        sys.stdout.flush()

      filepath, _ = urllib.request.urlretrieve(url, filepath, _progress)
      statinfo = os.stat(filepath)
      print('\nSuccessfully downloaded', filename, statinfo.st_size, 'bytes.')
      tarfile.open(filepath, 'r:gz').extractall(data_path)

def maybe_preprocess(data_path):
  base_path = os.path.join(data_path, 'MPIIGAZE_PATH/Data/Normalized')
  npz_path = os.path.join(data_path, DATA_FNAME)

  if os.path.exists(npz_path):
    return

  # MPIIGaze dataset
  mat_paths =[]
  for root, dirnames, filenames in os.walk(base_path):
    for filename in fnmatch.filter(filenames, '*.mat'):
      mat_paths.append(os.path.join(root, filename))

  images =[]
  for mat_path in tqdm(mat_paths):
    mat = loadmat(mat_path)
    # Left eye (batch_size, height, width)
    images.extend(mat['data'][0][0][0][0][0][1])
    # Right eye
    images.extend(mat['data'][0][0][1][0][0][1])

  real_data = np.stack(images, axis=0)

  # UnityEyes dataset
  synthetic_data = None

  #raise Exception("[!] Not implemented yet")

  np.savez(npz_path, real=real_data, synthetic=synthetic_data)
  print("[*] Preprocessing of `gaze` data is finished.")

def load(data_path, debug=False):
  if not os.path.exists(data_path):
    print('creating folder', data_path)
    os.makedirs(data_path)

  maybe_download_and_extract(data_path)
  maybe_preprocess(data_path)

  gaze_data = np.load(os.path.join(data_path, DATA_FNAME))

  real_data, synthetic_data = gaze_data['real'], gaze_data['synthetic']
  if debug:
    print("[*] Save sample images in {}".format(data_path))
    for idx in range(10):
      image_path = os.path.join(synthetic_images,
                                "sample_real_{}".format(idx))
      imwrite(image_path, real_data[idx])
  return real_data, synthetic_data

class DataLoader(object):
  def __init__(self, data_dir, batch_size, debug=False, rng=None):
    self.data_path = os.path.join(data_dir, 'gaze')
    self.batch_size = batch_size

    self.data, self.labels = load(self.data_path, conf.debug)
    self.data = np.transpose(self.data, (0,2,3,1)) # (N,3,32,32) -> (N,32,32,3)
    
    self.p = 0 # pointer to where we are in iteration
    self.rng = np.random.RandomState(1) if rng is None else rng


  def get_observation_size(self):
    return self.data.shape[1:]

  def get_num_labels(self):
    return np.amax(self.labels) + 1

  def reset(self):
    self.p = 0

  def __iter__(self):
    return self

  def __next__(self, n=None):
    """ n is the number of examples to fetch """
    if n is None: n = self.batch_size

    # on first iteration lazily permute all data
    if self.p == 0 and self.shuffle:
      inds = self.rng.permutation(self.data.shape[0])
      self.data = self.data[inds]
      self.labels = self.labels[inds]

    # on last iteration reset the counter and raise StopIteration
    if self.p + n > self.data.shape[0]:
      self.reset() # reset for next time we get called
      raise StopIteration

    # on intermediate iterations fetch the next batch
    x = self.data[self.p : self.p + n]
    y = self.labels[self.p : self.p + n]
    self.p += self.batch_size

    if self.return_labels:
      return x,y
    else:
      return x

  next = __next__
