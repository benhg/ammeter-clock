'use strict';
// Pure math shared with tests; a result outside the hardware range is never silently clamped.
function calibrationScale(code,target,reading){
  if(!Number.isFinite(reading)||reading<=0)throw new Error('Enter a positive needle reading.');
  const result=Math.round(code*target/reading);
  if(result<1||result>4095)throw new Error('That adjustment exceeds the available range. Check the meter rating and wiring.');
  return result;
}
if(typeof module!=='undefined')module.exports={calibrationScale};
