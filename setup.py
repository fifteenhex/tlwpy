from setuptools import setup
from Cython.Build import cythonize
from setuptools.extension import Extension

extensions = [
    Extension(
        'tlwpy.liblorawan',
        ['liblorawan/lorawan.pyx', 'liblorawan/crypto.c', 'liblorawan/packet.c'],
        libraries=['crypto'],
        extra_compile_args=['-std=gnu99']
    )
]

setup(name='tlwpy',
      version='0.1',
      author='Daniel Palmer',
      author_email='daniel@0x0f.com',
      license='GPLv3',
      packages=['tlwpy'],
      zip_safe=False,
      ext_modules=cythonize(extensions))
