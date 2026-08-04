// Ручной мок axios для тестов.
//
// Пакет поставляется в виде ESM, а jest из create-react-app не транспилирует
// node_modules — при попытке замокать axios автоматически тест падает на
// «Cannot use import statement outside a module». Ручной мок подставляется
// вместо настоящего пакета и эту загрузку исключает.
const axios = {
  create: jest.fn(),
  post: jest.fn(),
  get: jest.fn(),
  put: jest.fn(),
  patch: jest.fn(),
  delete: jest.fn(),
};

export default axios;
