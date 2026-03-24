export function progShow(id) {
    document.getElementById('prog' + id).style.display = 'block';
  }
  
  export function progSet(id, pct) {
    document.getElementById('prog' + id + 'Bar').style.width = pct + '%';
  }