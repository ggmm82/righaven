#!/usr/bin/env python3
"""Package a rebuilt software image for RigHaven's verified environment importer."""
import argparse,hashlib,json,subprocess,tarfile,tempfile
from pathlib import Path


def inspect(reference):
    return json.loads(subprocess.check_output(['docker','image','inspect',reference],text=True))[0]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image');parser.add_argument('--base');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parent
    recipe=json.loads((root/'recipe-files.json').read_text())
    image=inspect(args.image);base=inspect(args.base or recipe['software_image'])
    if image['RootFS']['Layers'][:len(base['RootFS']['Layers'])]!=base['RootFS']['Layers']:
        parser.error('L’immagine non deriva dalla base dichiarata')
    with tempfile.TemporaryDirectory(prefix='skill-package-') as directory:
        folder=Path(directory);saved=folder/'image.tar'
        from docker_image_archive import save_image
        info=save_image(args.image,image,saved)
        if saved.stat().st_size>16*1024**3:parser.error('Immagine oltre il limite di 16 GiB')
        digest=hashlib.sha256()
        with saved.open('rb') as stream:
            for block in iter(lambda:stream.read(1024**2),b''):digest.update(block)
        manifest={'format':'skill-software-environment','version':1,'software_id':base['Id'],
            'recipe':recipe['recipe'],'tools':recipe['tools'],'versions':recipe.get('versions',{}),'image_id':info['config_digest'],'image_config_digest':info['config_digest'],
            'source_image_id':image['Id'],'software_layers':base['RootFS']['Layers'],'layer_count':len(info['layers']),
            'image_bytes':saved.stat().st_size,'image_sha256':digest.hexdigest(),
            'os':image['Os'],'architecture':image['Architecture'],'variant':image.get('Variant','')}
        (folder/'manifest.json').write_text(json.dumps(manifest))
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with tarfile.open(args.output,'w') as archive:
            archive.add(saved,arcname='image.tar');archive.add(folder/'manifest.json',arcname='manifest.json')
            for name in [*recipe['files'],'recipe-files.json']:
                path=root/name
                if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or not path.resolve().is_relative_to(root):
                    raise ValueError('File della ricetta non valido')
                archive.add(path,arcname='rebuild/'+name,recursive=False)
    print(args.output)


if __name__=='__main__':main()
