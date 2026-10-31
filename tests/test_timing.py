import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import wave
from righaven.timing import check_timing
from real_tools import requires


@requires('ffmpeg')
class TimingTests(unittest.TestCase):
    def movie(self,root,event,continuous=False):
        source=root/('source-'+str(event)+'.wav');target=source.with_suffix('.mp4')
        with wave.open(str(source),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000)
            wav.writeframes(b''.join(struct.pack('<h',int(20000*math.sin(2*math.pi*1000*i/8000))
                if continuous or event<=i/8000<event+.04 else 0) for i in range(32000)))
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=black:s=32x32:r=25:d=4',
            '-i',str(source),'-vf',"drawbox=enable='between(t,1,1.04)':color=white:t=fill",'-c:v','libx264','-pix_fmt','yuv420p',
            '-c:a','aac','-shortest',str(target)],check=True,capture_output=True,timeout=30)
        return {'output_files':[str(target)],'delivery':{'timing':{'master':str(target),
            'cues':[{'name':'Declared visual event','visual_seconds':1,'tolerance_seconds':.12}]}}}

    def test_actual_master_with_equal_duration_but_delayed_sound_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            delayed=check_timing(self.movie(root,2.5),required=True)
            self.assertEqual(delayed['status'],'failed')
            self.assertAlmostEqual(delayed['cues'][0]['delta_seconds'],1.5,delta=.08)
            aligned=check_timing(self.movie(root,1.0),required=True)
            self.assertEqual(aligned['status'],'passed')
            self.assertLess(abs(aligned['cues'][0]['delta_seconds']),.12)

    def test_continuous_sound_is_not_a_verified_semantic_cue(self):
        with tempfile.TemporaryDirectory() as temp:
            result=check_timing(self.movie(Path(temp),0,continuous=True),required=True)
            self.assertEqual(result['status'],'not_run')
            self.assertTrue(result['issues'])

    def test_missing_contract_or_wrong_master_is_never_marked_verified(self):
        self.assertTrue(check_timing({},required=True)['issues'])
        self.assertFalse(check_timing({})['issues'])
        result=check_timing({'delivery':{'timing':{'master':'/outside.mp4','cues':[]}}},required=True)
        self.assertEqual(result['status'],'not_run')
