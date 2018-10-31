# -*- coding: utf-8 -*-
"""
    Tensorflow Keras API with TF Estimator class
    working on custom model of 10 monkey species dataset from Kaggle

"""

import tensorflow as tf
from keras.utils import to_categorical
import cv2 as cv
import glob
import sys
import os
import numpy as np
from tensorflow.keras.layers import Conv2D, GlobalAveragePooling2D, Flatten, Dense, Input
from tensorflow.keras.models import Model
from tensorflow.keras.applications.vgg16 import VGG16
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split

def _int64_feature(value):
  return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))

def _bytes_feature(value):
  return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

#Function to load image 
def load_image(addr):
  img = cv.imread(addr)
  if img is None:
    return None
  img = cv.resize(img, (224, 224), interpolation=cv.INTER_CUBIC)
  img = cv.cvtColor(img, cv.COLOR_BGR2RGB)
  return img

#Function to create TFRecords
def create_tfrecords(filename, address, labels):
  
  #Call the TFRecordWriter function class to write records to a TFRecords file and assign a writer function
  writer = tf.python_io.TFRecordWriter(filename)
  
  #Load images and labels
  for i in range(len(address)):
    img = load_image(address[i])
    label = labels[i]

    if img is None:
      continue
    
    #Create the feature dictionary with image_raw and label as keys and 
    #their bytes and int64 lists features as respective values
    feature = {
            'image_raw': _bytes_feature(img.tostring()),
            'label': _int64_feature(label)}
    
    #Instantiate an Example protocol message
    example = tf.train.Example(features=tf.train.Features(feature=feature))
    
    #Write the serialized string Example proto 
    writer.write(example.SerializeToString())
  
  #Close the writer after finishing writing TFRecords      
  writer.close()
  sys.stdout.flush()

#Creating labels from custom data
def create_labels():
  labels = []
  for i in os.listdir('training'):
    for l in enumerate(os.listdir('training/{}'.format(i))):
      labels.append(i)
  le = LabelEncoder()
  labels = le.fit_transform(labels)
  
  return labels

labels = create_labels()

#Generating image locations
train_path = 'training/*/*.jpg' #training/class/image.jpg
address = glob.glob(train_path)

#Splitting train and test data
x_train = address[0:int(0.8*len(address))]
y_train = labels[0:int(0.8*len(labels))]

x_test = address[int(0.8*len(address)):]
y_test = labels[int(0.8*len(labels)):]

create_tfrecords('mon_train.tfrecords', x_train, y_train)
create_tfrecords('mon_test.tfrecords', x_test, y_test)

def create_keras_model():
    
  #Keras pre-trainied VGG16 model
  base_model = VGG16(weights='imagenet', input_shape=(224,224,3), include_top=False)

  x = base_model.output
  #Do the global average pooling on the last layer of base_model
  x = GlobalAveragePooling2D()(x)
  x = Dense(512, activation='relu')(x)
  #Make the ouput layer with 10 neurons to represent 10 output classes
  output = Dense(10, activation='softmax')(x)
  #Instantiate the Model functional API class
  model = Model(inputs=base_model.input, outputs=output)

  num_layers = 0
  fine_tuning = False

  if fine_tuning:

    #Freezing the lower layer and making the rest trainable for fine-tuning                                            
    for layer in model.layers[:num_layers]:
      layer.trainable = False

    for layer in model.layers[num_layers:]:
      layer.trainable = True
  else:
    #Train only top layer for transer learning
    for layer in base_model.layers:
      layer.trainable = False

  #Define the optimizer    
  optimizer = tf.keras.optimizers.Adam(lr=1e-5)  
  #Compile the model 
  model.compile(optimizer=optimizer, loss='categorical_crossentropy', metrics=['accuracy'])

  #Convert the Keras model to Tensorflow Estimator instance
  keras_model = tf.keras.estimator.model_to_estimator(keras_model=model)

keras_model = create_keras_model()    
    
#Initiating session
sess = tf.Session()
sess.run(tf.global_variables_initializer())

#Defining parser function to extract from the TFRecord files
def parser(record):
  
  #Create a dictionary to extract the raw image and label from the TFRecord files
  keys_to_features = {
                        'image_raw': tf.FixedLenFeature([], tf.string),
                        'label': tf.FixedLenFeature([], tf.int64)}
                      
  #Parse the TFRecord files with the above created dictionary
  parsed = tf.parse_single_example(record, keys_to_features)
  #Decode the raw image  from the parser dictionary
  image = tf.decode_raw(parsed['image_raw'], tf.uint8)
  #Convert the image to float32 type
  image = tf.cast(image, tf.float32)
  #Reshape the extracted image to 224x224x3 shape as their original shape 
  image = tf.reshape(image, shape = [224, 224, 3])
  #Convert the lables to int32 type
  labels = tf.cast(parsed['label'], tf.int32)
  return image, labels

#Define the input function for the dataset pipeline
def inp_fn(filename, train, batch_size=64, buffer_size=1000):
  
  #Read the dataset from the TFRecord file
  dataset = tf.data.TFRecordDataset(filenames=filename)
  
  #Map the parser function to the read dataset to get the image and labels
  dataset = dataset.map(parser)
  
  #If training, shuffle the dataset, else not
  if train:
    dataset = dataset.shuffle(buffer_size=buffer_size)
    num_repeat = None
  
  else:
    num_repeat = 1
  
  #Repeat the dataset indefinitely for training and only once for testing
  #Number of repeats can be passed by argument if not to repeat indefinitely
  dataset = dataset.repeat(num_repeat)
  #Combines consecutive elements of this dataset into batches
  dataset = dataset.batch(batch_size=batch_size)
  #Initialize the one shot iterator to creates an Iterator for enumerating the elements of this dataset
  iterator = dataset.make_one_shot_iterator()
  #Get the next batch of data
  images_batch, labels_batch = iterator.get_next()
    
  x = images_batch
  y = labels_batch
    
  return x, y

#Train Input Function
def train_input_fn():
  return inp_fn(filename='train.tfrecords' , train=True)

#Test Input Function
def test_input_fn():
   return inp_fn(filename='test.tfrecords', train=False)

  
#Train and evaluate the model
keras_model.train(input_fn=train_input_fn, steps=10000)
result = keras_model.evaluate(input_fn=test_input_fn)
print('Result:', result)
print('Classification Accuracy : {:4f}'.format(result['accuracy']*100)) 
print('Classification loss: {:.4f}'.format(result['loss']))
