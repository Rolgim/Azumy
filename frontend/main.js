import { initFind, runFind, sendToRetrieve } from './find.js';
import { runRetrieve }                        from './retrieve.js';

document.getElementById('btnFind').addEventListener('click', runFind);
document.getElementById('btnSendRetrieve').addEventListener('click', sendToRetrieve);
document.getElementById('btnRetrieve').addEventListener('click', runRetrieve);

// Init map on page load
initFind();