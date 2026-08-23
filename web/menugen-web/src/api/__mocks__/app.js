// MG_APKSITE: мок публичного API приложения — как и остальные моки в этой
// папке, он избавляет тесты от загрузки настоящего axios-клиента.
const appApi = { androidBuild: jest.fn(() => Promise.resolve({ data: { build: null } })) };
module.exports = { appApi };
module.exports.default = { appApi };
