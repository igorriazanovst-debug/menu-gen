// MG_PAYPERIOD: выбор периода подписки.
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { PeriodPicker, offerPriceNote } from './PeriodPicker';
import type { PlanOffer } from '../../types';

const month: PlanOffer = {
  code: 'premium_month', title: 'Месяц', months: 1, price: '299.00',
  price_per_month: '299.00', discount_percent: 0, plan_code: 'premium',
};
const year: PlanOffer = {
  code: 'premium_year', title: 'Год', months: 12, price: '2990.00',
  price_per_month: '249.17', discount_percent: 17, plan_code: 'premium',
};

describe('PeriodPicker', () => {
  it('показывает периоды и выгоду длинного', () => {
    render(<PeriodPicker offers={[month, year]} value="premium_month" onChange={() => {}} />);

    expect(screen.getByText('Месяц')).toBeTruthy();
    expect(screen.getByText('Год')).toBeTruthy();
    expect(screen.getByText('−17%')).toBeTruthy();
  });

  it('отмечает выбранный период', () => {
    render(<PeriodPicker offers={[month, year]} value="premium_year" onChange={() => {}} />);

    const selected = screen.getAllByRole('radio').filter((el) => el.getAttribute('aria-checked') === 'true');
    expect(selected).toHaveLength(1);
    expect(selected[0].textContent).toContain('Год');
  });

  it('сообщает о выборе', () => {
    const onChange = jest.fn();
    render(<PeriodPicker offers={[month, year]} value="premium_month" onChange={onChange} />);

    fireEvent.click(screen.getByText('Год'));

    expect(onChange).toHaveBeenCalledWith('premium_year');
  });

  it('единственный период выбирать не из чего', () => {
    // Иначе на бесплатном тарифе висел бы бессмысленный переключатель.
    const { container } = render(<PeriodPicker offers={[month]} value="premium_month" onChange={() => {}} />);

    expect(container.innerHTML).toBe('');
  });
});

describe('offerPriceNote', () => {
  it('для длинного периода показывает цену за месяц', () => {
    expect(offerPriceNote(year)).toBe('249 ₽ в месяц');
  });

  it('для месяца сравнивать не с чем', () => {
    expect(offerPriceNote(month)).toBeNull();
  });
});
