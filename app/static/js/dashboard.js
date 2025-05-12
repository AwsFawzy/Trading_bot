// تحديث البيانات تلقائيًا كل 30 ثانية
window.addEventListener('DOMContentLoaded', (event) => {
    // تحديث البيانات مباشرة عند تحميل الصفحة
    updateDashboardData();
    
    // ضبط تحديث دوري
    setInterval(updateDashboardData, 30000);
});

// دالة لتحديث البيانات من الخادم
function updateDashboardData() {
    // سجل للتصحيح
    console.log("Updating dashboard data...");
    
    // إذا كانت تحديثات العملات المراقبة متاحة
    if (typeof loadWatchedCoins === 'function') {
        loadWatchedCoins();
    }
}