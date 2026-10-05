import {day} from './encodings.mjs';
const months=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];
export function dateAxis(label,referenceDate){
  const match=String(label).trim().match(/^([A-Za-z]+)\s+(\d{1,2})(?:,?\s+(\d{4}))?\s*[—–-]\s*([A-Za-z]+)\s+(\d{1,2})(?:,?\s+(\d{4}))?$/);
  if(!match)return null;
  const year=Number(match[3]||String(referenceDate||'').slice(0,4));
  if(!Number.isInteger(year)||year<1)return null;
  const fromMonth=months.indexOf(match[1].slice(0,3).toLowerCase()),toMonth=months.indexOf(match[4].slice(0,3).toLowerCase());
  if(fromMonth<0||toMonth<0)return null;
  const iso=(y,m,d)=>String(y).padStart(4,'0')+'-'+String(m+1).padStart(2,'0')+'-'+String(d).padStart(2,'0');
  const from=iso(year,fromMonth,match[2]),to=iso(Number(match[6]||year),toMonth,match[5]);
  const start=day(from),end=day(to);if(start===null||end===null||end<start||end-start>3660)return null;
  return {from,to,origin:start,days:end-start+1,snap:1};
}
