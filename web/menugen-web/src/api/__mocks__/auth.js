const authApi = {
  login: jest.fn(),
  me: jest.fn(),
  logout: jest.fn(),
  register: jest.fn(),
  updateMe: jest.fn(),
  // MG_PHONEVERIFY
  loginPhone: jest.fn(),
  phoneStart: jest.fn(),
  phoneStatus: jest.fn(),
  phoneRegister: jest.fn(),
};
module.exports = { authApi };
