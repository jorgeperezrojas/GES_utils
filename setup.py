from distutils.core import setup

setup(
	name='Ges_utils',
	version='1.0',
	description='Utilidades para trabajar con datos de texto GES',
	author='Jorge Pérez, Fabian Villena',
	author_email='jorge.perez.rojas@gmail.com',
	url='https://github.com/jorgeperezrojas/GES_utils',
 	packages=['ges_utils'],
 	package_dir={'ges_utils': 'ges_utils'},
 	package_data={'ges_utils': ['data/*.json']}
 )
