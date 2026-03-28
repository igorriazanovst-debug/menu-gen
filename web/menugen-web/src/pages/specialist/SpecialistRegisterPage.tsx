import React from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAppDispatch, useAppSelector } from "../../hooks/useAppDispatch";
import { registerAsSpecialist } from "../../store/specialistSlice";

const schema = z.object({
  specialist_type: z.enum(["dietitian", "trainer"]),
});

type FormValues = z.infer<typeof schema>;

export const SpecialistRegisterPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { error } = useAppSelector((s) => s.specialist);

  const {
    register,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { specialist_type: "dietitian" },
  });

  const onSubmit = async (values: FormValues) => {
    await dispatch(registerAsSpecialist(values.specialist_type)).unwrap();
    navigate("/specialist");
  };

  return (
    <div className="max-w-md mx-auto mt-16 px-4">
      <h1 className="text-2xl font-bold text-chocolate mb-2">
        Регистрация как специалист
      </h1>
      <p className="text-sm text-gray-400 mb-8">
        После регистрации профиль проходит верификацию администратором.
      </p>

      <form
        onSubmit={handleSubmit(onSubmit)}
        className="bg-white rounded-2xl shadow p-6 space-y-5"
      >
        <div>
          <label className="block text-sm font-medium text-chocolate mb-2">
            Специализация
          </label>
          <select
            {...register("specialist_type")}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-avocado"
          >
            <option value="dietitian">Диетолог</option>
            <option value="trainer">Тренер</option>
          </select>
        </div>

        {error && <p className="text-tomato text-sm">{error}</p>}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full bg-tomato text-white py-3 rounded-xl font-semibold hover:bg-red-700 disabled:opacity-50"
        >
          {isSubmitting ? "Отправка..." : "Подать заявку"}
        </button>
      </form>
    </div>
  );
};
