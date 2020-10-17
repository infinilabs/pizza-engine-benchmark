(this["webpackJsonpsearch-benchmark"]=this["webpackJsonpsearch-benchmark"]||[]).push([[0],{14:function(e,t,a){},15:function(e,t,a){"use strict";a.r(t);var n=a(1),r=a(4),l=a(5),o=a(8),i=a(7),u=a(0),c=a.n(u),s=a(2),m=a.n(s),d=a(6),v=a.n(d);a(14),Boolean("localhost"===window.location.hostname||"[::1]"===window.location.hostname||window.location.hostname.match(/^127(?:\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}$/));function f(e){e=e.toString();for(var t=/(-?\d+)(\d{3})/;t.test(e);)e=e.replace(t,"$1,$2");return e}function h(e){if(0==e.duration.length)return{query:e.query,className:"unsupported",unsupported:!0};var t,a={median:(t=e.duration)[t.length/2|0],mean:t.reduce((function(e,t){return e+t}),0)/t.length,min:t[0],max:t[t.length-1]};return a.count=e.count,a.query=e.query,a}var p=function(e){Object(o.a)(a,e);var t=Object(i.a)(a);function a(e){var n;return Object(r.a)(this,a),(n=t.call(this,e)).state={mode:"TOP_10",tag:null},n}return Object(l.a)(a,[{key:"handleChangeMode",value:function(e){this.setState({mode:e.target.value})}},{key:"handleChangeTag",value:function(e){var t=e.target.value;"ALL"==t?this.setState({tag:null}):this.setState({tag:t})}},{key:"filterQueries",value:function(e){var t=this.state.tag;return void 0!=t?e.filter((function(e){return e.tags.indexOf(t)>=0})):e}},{key:"generateDataView",value:function(){return{}}},{key:"generateDataView",value:function(){var e={},t={},a=this.props.data[this.state.mode];for(var r in a){var l=a[r];l=(l=Array.from(this.filterQueries(l))).map(h);var o,i=0,u=!1,c=Object(n.a)(l);try{for(c.s();!(o=c.n()).done;){(d=o.value).unsupported?u=!0:i+=d.min}}catch(b){c.e(b)}finally{c.f()}i=u?void 0:i/l.length|0,e[r]=i;var s,m=Object(n.a)(l);try{for(m.s();!(s=m.n()).done;){var d=s.value,v={};void 0!=t[d.query]&&(v=t[d.query]),v[r]=d,t[d.query]=v}}catch(b){m.e(b)}finally{m.f()}}for(var d in t){v=t[d];var f=null,p=0,g=null,y=0;for(var r in v){(E=v[r]).unsupported||((null==f||E.min<p)&&(f=r,p=E.min),(null==g||E.min>y)&&(g=r,y=E.min))}for(var r in v){var E;(E=v[r]).unsupported||r!=f&&(E.variation=(E.min-p)/p)}null!=f&&(v[f].className="fastest",v[g].className="slowest")}return{engines:e,queries:t}}},{key:"render",value:function(){var e=this,t=this.generateDataView();return c.a.createElement("div",null,c.a.createElement("form",null,c.a.createElement("fieldset",null,c.a.createElement("label",{htmlFor:"collectionField"},"Collection type"),c.a.createElement("select",{id:"collectionField",onChange:function(t){return e.handleChangeMode(t)}},this.props.modes.map((function(e){return c.a.createElement("option",{value:e,key:e},e)}))),c.a.createElement("label",{htmlFor:"queryTagField"},"Type of Query"),c.a.createElement("select",{id:"queryTagField",onChange:function(t){return e.handleChangeTag(t)}},c.a.createElement("option",{value:"ALL",key:"all"},"ALL"),this.props.tags.map((function(e){return c.a.createElement("option",{value:e,key:e},e)}))))),c.a.createElement("hr",null),c.a.createElement("table",null,c.a.createElement("thead",null,c.a.createElement("tr",null,c.a.createElement("th",null,"Query"),Object.keys(t.engines).map((function(e){return c.a.createElement("th",{key:"col-"+e},e)})))),c.a.createElement("tbody",null,c.a.createElement("tr",{className:"average-row"},c.a.createElement("td",null,"AVERAGE"),Object.entries(t.engines).map((function(e){var t=e[0],a=e[1];return void 0!=a?c.a.createElement("td",{key:"result-"+t},f(a)," \u03bcs"):c.a.createElement("td",{key:"result-"+t},"Some Unsupported Queries")}))),Object.entries(t.queries).map((function(e){var a=e[0],n=e[1];return c.a.createElement("tr",null,c.a.createElement("td",null,a),Object.keys(t.engines).map((function(e){var t,a=n[e];return a.unsupported?c.a.createElement("td",{className:"data "+a.className}):c.a.createElement("td",{className:"data "+a.className},c.a.createElement("div",{className:"timing"},f(a.min),"  \u03bcs"),c.a.createElement("div",{className:"timing-variation"},void 0!=(t=a.variation)?"+"+(100*t).toFixed(1)+" %":""),c.a.createElement("div",{className:"count"},f(a.count)," docs"))})))})))))}}]),a}(c.a.Component);m()((function(){m.a.getJSON("/results.json",(function(e){var t=[],a=[],r=new Set,l=[];for(var o in e)t.push(o);for(var i in e[t[0]])a.push(i);var u,s=Object(n.a)(e[t[0]][a[0]]);try{for(s.s();!(u=s.n()).done;){var m,d=u.value,f=Object(n.a)(d.tags);try{for(f.s();!(m=f.n()).done;){var h=m.value;r.add(h)}}catch(y){f.e(y)}finally{f.f()}}}catch(y){s.e(y)}finally{s.f()}(l=Array.from(r)).sort();var g=document.getElementById("app-container");v.a.render(c.a.createElement(c.a.StrictMode,null,c.a.createElement(p,{data:e,tags:l,modes:t,engines:a})),g)}))})),"serviceWorker"in navigator&&navigator.serviceWorker.ready.then((function(e){e.unregister()})).catch((function(e){console.error(e.message)}))},9:function(e,t,a){e.exports=a(15)}},[[9,1,2]]]);
//# sourceMappingURL=main.c66c7816.chunk.js.map