const authApi = {
  login: jest.fn(),
  me: jest.fn(),
  logout: jest.fn(),
  register: jest.fn(),
  updateMe: jest.fn(),
};
module.exports = { authApi };
