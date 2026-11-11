import sys,unittest
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/clock_setup'))
from timezones import schedule,zone_names

def epoch(y,m,d,h=0):return int(datetime(y,m,d,h,tzinfo=timezone.utc).timestamp())
def planned(plan,at):
 result=plan['offset']
 for when,offset in plan['changes']:
  if when>at:break
  result=offset
 return result
class TimeZoneTests(unittest.TestCase):
 def test_global_list_and_fractional_offsets(self):
  self.assertGreater(len(zone_names()),500)
  self.assertEqual(planned(schedule('Asia/Kathmandu',epoch(2026,11,10)),epoch(2026,11,10)),345)
  self.assertEqual(planned(schedule('Pacific/Chatham',epoch(2026,11,10)),epoch(2026,11,10)),825)
 def test_us_and_southern_half_hour_dst(self):
  p=schedule('America/Los_Angeles',epoch(2026,11,10));spring=epoch(2026,3,8,10)
  self.assertEqual(planned(p,spring-1),-480);self.assertEqual(planned(p,spring),-420)
  p=schedule('Australia/Lord_Howe',epoch(2026,11,10))
  self.assertEqual(planned(p,epoch(2026,1,1)),660);self.assertEqual(planned(p,epoch(2026,7,1)),630)
 def test_no_dst_and_bounds(self):
  p=schedule('UTC',epoch(2026,11,10));self.assertEqual(p['changes'],[])
  self.assertLessEqual(p['until'],4102444800)
  with self.assertRaises(ValueError):schedule('Not/AZone',epoch(2026,11,10))
if __name__=='__main__':unittest.main()
