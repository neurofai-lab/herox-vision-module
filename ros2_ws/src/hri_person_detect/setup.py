from glob import glob
from setuptools import find_packages, setup

package_name = 'hri_person_detect'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*')),
        ('share/' + package_name + '/models', glob('models/*')),
        ('share/' + package_name + '/module', glob('module/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Shino Sam',
    maintainer_email='shino.sam@dfki.de',
    description='ROS2 person-only RTMDet/DeepSort/Realsense 3D bounding box publisher.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'hri_person_detect = hri_person_detect.node_person_detector:main',
        ],
    },
)
