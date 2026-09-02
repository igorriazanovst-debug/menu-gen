// MG_PHONECODE: разбор номера и три способа его ввести.
//
// Проверяется ровно то, что легко сломать незаметно: склейка кода с номером
// (иначе получается «+7+7…»), вставка номера целиком и российская «восьмёрка».
import '@testing-library/jest-dom';

import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { PhoneInput, splitPhone, DEFAULT_PHONE_CODE } from './PhoneInput';

const Harness: React.FC<{ initial?: string }> = ({ initial = DEFAULT_PHONE_CODE }) => {
  const [value, setValue] = useState(initial);
  return (
    <>
      <PhoneInput value={value} onChange={setValue} />
      <span data-testid="value">{value}</span>
    </>
  );
};

describe('splitPhone', () => {
  it('пустая строка — код по умолчанию', () => {
    expect(splitPhone('')).toEqual({ code: '+7', rest: '' });
  });

  it('российский номер', () => {
    expect(splitPhone('+79123456789')).toEqual({ code: '+7', rest: '9123456789' });
  });

  it('длинный код не съедается коротким', () => {
    // «+375…» не должно разобраться как «+3» или «+37»: коды примеряются от
    // длинных к коротким.
    expect(splitPhone('+375291234567')).toEqual({ code: '+375', rest: '291234567' });
  });

  it('оформление номера отбрасывается', () => {
    expect(splitPhone('+7 (912) 345-67-89')).toEqual({ code: '+7', rest: '9123456789' });
  });
});

describe('PhoneInput', () => {
  it('код страны подставлен заранее', () => {
    render(<Harness />);
    expect(screen.getByTestId('value')).toHaveTextContent('+7');
    expect(screen.getByLabelText('Код страны')).toHaveValue('+7');
  });

  it('набранные цифры склеиваются с кодом', () => {
    render(<Harness />);
    fireEvent.change(screen.getByLabelText('Телефон'), { target: { value: '9123456789' } });
    expect(screen.getByTestId('value')).toHaveTextContent('+79123456789');
  });

  it('смена страны сохраняет набранный номер', () => {
    render(<Harness />);
    fireEvent.change(screen.getByLabelText('Телефон'), { target: { value: '291234567' } });
    fireEvent.change(screen.getByLabelText('Код страны'), { target: { value: '+375' } });
    expect(screen.getByTestId('value')).toHaveTextContent('+375291234567');
  });

  it('вставка номера целиком не удваивает код', () => {
    render(<Harness />);
    fireEvent.change(screen.getByLabelText('Телефон'), { target: { value: '+375291234567' } });
    expect(screen.getByTestId('value')).toHaveTextContent('+375291234567');
    expect(screen.getByLabelText('Код страны')).toHaveValue('+375');
  });

  it('восьмёрка вместо +7', () => {
    render(<Harness />);
    fireEvent.change(screen.getByLabelText('Телефон'), { target: { value: '89123456789' } });
    expect(screen.getByTestId('value')).toHaveTextContent('+79123456789');
  });
});
