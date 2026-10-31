"""Install curated optional upstream distributions inside preparation only."""
from pathlib import Path
import shutil,subprocess,xml.etree.ElementTree as ET


def repository(app,root,download):
    """Only reviewed catalog repositories, scoped by signed-by; no user shell input."""
    repo=app.get('install',{}).get('apt_repository')
    if not repo:return
    known={
      'bookworm-backports':('https://deb.debian.org/debian','bookworm-backports','main'),
      'openmodelica':('https://build.openmodelica.org/apt','bookworm','stable'),
    }
    if repo['id'] not in known or tuple(repo[k] for k in ('url','suite','component'))!=known[repo['id']]:
        raise ValueError('Unreviewed APT repository')
    key='/usr/share/keyrings/debian-archive-keyring.gpg'
    if repo['id']=='openmodelica':
        key=str(root/'openmodelica-keyring.asc');download(repo['key'],Path(key))
    Path('/etc/apt/sources.list.d/righaven-'+repo['id']+'.list').write_text(
      f"deb [signed-by={key}] {repo['url']} {repo['suite']} {repo['component']}\n")


def install(app,archive,destination,root,bin_dir,arch,base):
    kind=app['install']['kind'];destination.mkdir(parents=True,exist_ok=True)
    repository(app,root,base.download)
    if kind=='extended-native':
        if app['install'].get('raw_binary'):
            # Some upstreams publish the executable itself; its sha256 was already verified on download.
            shutil.copy2(archive,destination/app['install']['native_binary'])
        elif archive.name.endswith('.zip'):base.safe_unzip(archive,destination)
        else:base.safe_extract(archive,destination)
        name=app['install']['native_binary']
        matches=[p for p in destination.rglob(name) if p.is_file() and p.resolve().is_relative_to(destination.resolve())]
        if len(matches)!=1:raise ValueError('Expected one upstream executable: '+name)
        binary=matches[0];binary.chmod(binary.stat().st_mode|0o111)
        if app['id']=='zap':
            # Distribution scripts locate their jars relative to their actual path.
            return str(binary)
        link=bin_dir/('usql' if app['id']=='usql' else name)
        if link.exists() or link.is_symlink():raise ValueError('Existing native executable: '+str(link))
        link.symlink_to(binary);return str(binary)
    if kind=='verapdf-installer':
        unpack=destination/'installer';base.safe_unzip(archive,unpack)
        jars=list(unpack.rglob('*.jar'))
        if len(jars)!=1:raise ValueError('Expected the official veraPDF installer JAR')
        config=ET.Element('AutomatedInstallation',langpack='eng')
        ET.SubElement(config,'com.izforge.izpack.panels.htmlhello.HTMLHelloPanel',id='welcome')
        target=ET.SubElement(config,'com.izforge.izpack.panels.target.TargetPanel',id='install_dir')
        ET.SubElement(target,'installpath').text=str(destination/'runtime')
        packs=ET.SubElement(config,'com.izforge.izpack.panels.packs.PacksPanel',id='sdk_pack_select')
        for i,name in enumerate(['veraPDF GUI','veraPDF CLI','veraPDF Documentation','veraPDF Sample Plugins']):
            ET.SubElement(packs,'pack',index=str(i),name=name,selected='true' if i==1 else 'false')
        ET.SubElement(config,'com.izforge.izpack.panels.install.InstallPanel',id='install')
        ET.SubElement(config,'com.izforge.izpack.panels.finish.FinishPanel',id='finish')
        file=destination/'auto-install.xml';ET.ElementTree(config).write(file,encoding='utf-8',xml_declaration=True)
        subprocess.run(['java','-Djava.awt.headless=true','-jar',str(jars[0]),str(file)],check=True,timeout=300)
        binary=destination/'runtime/verapdf'
        if not binary.is_file():raise ValueError('veraPDF CLI missing after installation')
        binary.chmod(binary.stat().st_mode|0o111);return str(binary)
    if kind=='extension-node':
        for name in ('package.json','package-lock.json'):shutil.copy2(root/'toolkit-lock/extended'/app['id']/name,destination/name)
        subprocess.run(['npm','ci','--prefix',str(destination),'--ignore-scripts','--no-audit','--no-fund'],check=True)
        return str(destination/'package.json')
    raise ValueError('Unknown optional distribution: '+kind)
