window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());
(function(){
var PID='14',PNAME='고요나 블루이어 사운드 헤어밴드',PPRICE=89000;
// first-touch UTM 30일
try{var q=new URLSearchParams(location.search),ft=JSON.parse(localStorage.getItem('__gy_ft')||'null')||{},ch=false;
['utm_source','utm_medium','utm_campaign','fbclid','gclid'].forEach(function(k){var v=q.get(k);if(v&&!ft[k]){ft[k]=v;ch=true;}});
if(ch){ft.ts=Date.now();localStorage.setItem('__gy_ft',JSON.stringify(ft));}
if(ft.ts&&Date.now()-ft.ts>2592000000)localStorage.removeItem('__gy_ft');}catch(e){}
// 회원 ID → GA4 user_id
var mid=null;try{if(window.EC_SDE_SESSION&&EC_SDE_SESSION.member_id)mid=EC_SDE_SESSION.member_id;
else if(window.MEMBER_ID)mid=MEMBER_ID;
else{var m=document.cookie.match(/(?:^|;\s*)(?:mid|MEMBER_ID|sMemberID)=([^;]+)/);if(m)mid=decodeURIComponent(m[1]);}
if(mid)localStorage.setItem('goyona_mid',mid);else mid=localStorage.getItem('goyona_mid');}catch(e){}
var cfg={};if(mid)cfg.user_id=mid;
gtag('config','G-W0SK5SFEPE',cfg);gtag('config','AW-17989041512');
var sent=false,atcDeb=0;
function toI(v){return parseInt(String(v||'').replace(/[^0-9]/g,''),10)||0;}
function pname(){var e=document.querySelector('.headingArea h2')||document.querySelector('.headingArea h1')||document.querySelector('[class*="prd_name"]')||document.querySelector('h2');return e?e.textContent.trim():PNAME;}
function pprice(){var e=document.querySelector('#span_product_price_text')||document.querySelector('.price');return e?(toI(e.textContent)||PPRICE):PPRICE;}
function pid(){var m=location.pathname.match(/\/product\/[^/]+\/(\d+)/);return m?m[1]:PID;}
function isOrderDone(){var p=(location.pathname+location.search).toLowerCase();return p.indexOf('order_result')>-1||p.indexOf('order/result')>-1||p.indexOf('order_complete')>-1||p.indexOf('orderresult')>-1||p.indexOf('naverpay_result')>-1||p.indexOf('naverpay/result')>-1||p.indexOf('kakaopay_result')>-1||p.indexOf('kakaopay/result')>-1||p.indexOf('tosspayments/result')>-1||p.indexOf('payment_complete')>-1;}
function isCartUrl(u){if(!u)return false;u=u.toLowerCase();return u.indexOf('add_basket')>-1||u.indexOf('order_basket')>-1||u.indexOf('/exec/front/order/basket')>-1||u.indexOf('basket.html')>-1;}
function extractOrder(){var o='',t=0,items=[];
try{var sp=new URLSearchParams(location.search);o=sp.get('order_id')||sp.get('order_no')||sp.get('orderId')||'';var pv=sp.get('settle_price')||sp.get('total_price')||sp.get('amount');if(pv)t=toI(pv);}catch(e){}
try{var ext=window.EC_FRONT_EXTERNAL_SCRIPT_VARIABLE_DATA||window.EC_FRONT_EXTERNAL_SCRIPT_VARIABLE_DATA_ORDER||null;
if(ext){if(!o)o=String(ext.order_id||ext.order_no||'');if(!t)t=toI(ext.settle_price)||toI(ext.total_price)||toI(ext.payment_amount)||toI(ext.actual_payment_amount);
if(Array.isArray(ext.items)&&ext.items.length){items=ext.items.map(function(it){return{item_id:String(it.product_no||it.item_id||PID),item_name:it.product_name||it.item_name||PNAME,price:toI(it.product_price||it.price)||PPRICE,quantity:toI(it.quantity)||1,currency:'KRW'};});}}}catch(e){}
if(!t){var cs=document.querySelectorAll('strong,.total,[class*="total"],[class*="price"],[class*="payment"]');
for(var k=0;k<cs.length;k++){var tt=cs[k].textContent||'';if(tt.indexOf('총')===-1&&tt.indexOf('결제')===-1&&tt.indexOf('합계')===-1)continue;
var mm=tt.match(/([0-9,]{4,})\s*원/);if(mm){var v=toI(mm[1]);if(v>=1000&&v>t)t=v;}}}
if(!items.length){var qty=(t&&t%PPRICE===0)?t/PPRICE:1;items=[{item_id:PID,item_name:PNAME,price:PPRICE,quantity:qty,currency:'KRW'}];}
if(!o){var tk='goyona_fo_'+new Date().toISOString().slice(0,10);try{o=localStorage.getItem(tk)||('goyona_'+Date.now());localStorage.setItem(tk,o);}catch(e){o='goyona_'+Date.now();}}
return{o:o,t:t,items:items};}
function sendPurchase(){if(sent)return;var d=extractOrder();if(!d.t)return;
var sk='ga4_purchase_'+d.o;try{if(sessionStorage.getItem(sk)||localStorage.getItem(sk)){sent=true;return;}}catch(e){}
gtag('event','purchase',{transaction_id:d.o,value:d.t,currency:'KRW',items:d.items,transport_type:'beacon'});
gtag('event','conversion',{send_to:'AW-17989041512/eDKHCKfii5QcEOj664FD',value:d.t,currency:'KRW',transaction_id:d.o,transport_type:'beacon'});
try{if(typeof fbq==='function')fbq('track','Purchase',{value:d.t,currency:'KRW',contents:d.items.map(function(i){return{id:i.item_id,quantity:i.quantity};}),content_type:'product'});}catch(e){}
try{sessionStorage.setItem(sk,'1');localStorage.setItem(sk,'1');}catch(e){}sent=true;}
function sendATC(){var n=Date.now();if(n-atcDeb<1500)return;atcDeb=n;
var nm=pname(),pr=pprice(),pi=pid();
gtag('event','add_to_cart',{currency:'KRW',value:pr,items:[{item_id:pi,item_name:nm,price:pr,quantity:1,currency:'KRW'}]});
try{if(typeof fbq==='function')fbq('track','AddToCart',{value:pr,currency:'KRW',content_ids:[pi],content_type:'product'});}catch(e){}}
function run(){
if(isOrderDone()){sendPurchase();[500,1500,3000,5000,8000].forEach(function(x){setTimeout(sendPurchase,x);});
window.addEventListener('pagehide',sendPurchase);window.addEventListener('beforeunload',sendPurchase);
window.addEventListener('message',function(ev){var d=ev&&ev.data;if(!d)return;var s=typeof d==='string'?d:JSON.stringify(d);if(s&&(s.indexOf('payment')>-1||s.indexOf('success')>-1||s.indexOf('complete')>-1))setTimeout(sendPurchase,500);});}
if(location.pathname.indexOf('/product/')>-1&&location.pathname.indexOf('/product/list')===-1){setTimeout(function(){var nm=pname(),pr=pprice(),pi=pid();
gtag('event','view_item',{currency:'KRW',value:pr,items:[{item_id:pi,item_name:nm,price:pr,quantity:1,currency:'KRW'}]});
try{if(typeof fbq==='function')fbq('track','ViewContent',{value:pr,currency:'KRW',content_ids:[pi],content_type:'product'});}catch(e){}},1500);}
if(location.pathname.indexOf('/order/basket')>-1)setTimeout(function(){gtag('event','view_cart',{currency:'KRW'});},1000);
if(location.pathname.indexOf('/order/orderform')>-1)setTimeout(function(){var nm=pname(),pr=pprice(),pi=pid();gtag('event','begin_checkout',{currency:'KRW',value:pr,items:[{item_id:pi,item_name:nm,price:pr,quantity:1,currency:'KRW'}]});},1000);
var p2=location.pathname.toLowerCase();if(p2.indexOf('/member/join_result')>-1||p2.indexOf('/member/welcome')>-1||p2.indexOf('join_confirm')>-1){var jk='ga4_signup_'+new Date().toDateString();try{if(!sessionStorage.getItem(jk)){gtag('event','sign_up',{method:'cafe24'});sessionStorage.setItem(jk,'1');}}catch(e){gtag('event','sign_up',{method:'cafe24'});}}
var oo=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(m,u){if(isCartUrl(u))this.addEventListener('load',function(){if(this.status>=200&&this.status<400)sendATC();});return oo.apply(this,arguments);};
if(window.fetch){var of=window.fetch;window.fetch=function(i,ii){var u=typeof i==='string'?i:(i&&i.url)||'';var ic=isCartUrl(u);var pr=of.apply(this,arguments);if(ic)pr.then(function(r){if(r&&r.ok)sendATC();}).catch(function(){});return pr;};}
document.addEventListener('submit',function(e){var f=e.target;if(!f||f.tagName!=='FORM')return;var a=(f.getAttribute('action')||'').toLowerCase();var mi=f.querySelector('input[name="mode"]');var md=mi?(mi.value||'').toLowerCase():'';if(isCartUrl(a)||md==='add_basket'||md.indexOf('basket')>-1)sendATC();},true);
document.addEventListener('click',function(e){var t=e.target;if(!t)return;var el=t.closest?t.closest('a,button,input,img'):null;if(!el)return;
var tx=(el.textContent||el.value||el.alt||'').toLowerCase();var hr=(el.getAttribute&&el.getAttribute('href')||'').toLowerCase();var oc=(el.getAttribute&&el.getAttribute('onclick')||'').toLowerCase();
var id=(el.id||'').toLowerCase();var cl=(el.className||'').toString().toLowerCase();
if(tx.indexOf('장바구니')>-1||id.indexOf('basket')>-1||cl.indexOf('basket')>-1||cl.indexOf('cart')>-1||hr.indexOf('basket')>-1||oc.indexOf('basket')>-1)setTimeout(sendATC,100);},true);
var wi=setInterval(function(){if(typeof window.product_action==='function'&&!window.product_action._wrapped){var og=window.product_action;window.product_action=function(ty){if(ty==='basket')sendATC();return og.apply(this,arguments);};window.product_action._wrapped=true;clearInterval(wi);}},500);
setTimeout(function(){clearInterval(wi);},10000);}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run);else run();
})();