import React, { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import {
  createRecommendation,
  fetchClientRecommendations,
  deleteRecommendation,
} from "../../store/specialistSlice";

const schema = z.object({
  rec_type: z.enum(["supplement", "food", "exercise", "other"]),
  name: z.string().min(1, "Обязательное поле"),
  dosage: z.string().optional(),
  frequency: z.string().optional(),
  start_date: z.string().optional(),
  end_date: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

const TYPE_OPTIONS = [
  { value: "supplement", label: "БАД" },
  { value: "food", label: "Питание" },
  { value: "exercise", label: "Упражнение" },
  { value: "other", label: "Другое" },
];

export const RecommendationFormPage: React.FC = () => {
  const { familyId } = useParams<{ familyId: string }>();
  const fid = Number(familyId);
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { selectedClientRecs, loading } = useAppSelector((s) => s.specialist);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { rec_type: "supplement" },
  });

  useEffect(() => {
    dispatch(fetchClientRecommendations(fid));
  }, [dispatch, fid]);

  const onSubmit = async (values: FormValues) => {
    await dispatch(createRecommendation({ familyId: fid, data: values })).unwrap();
    navigate(`/specialist/clients/${fid}`);
  };

  const handleDelete = (recId: number) => {
    if (!window.confirm("Деактивировать рекомендацию?")) return;
    dispatch(deleteRecommendation({ familyId: fid, recId }));
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      <Link
        to={`/specialist/clients/${fid}`}
        className="text-sm text-avocado hover:underline mb-2 inline-block"
      >
        ← Назад
      </Link>
      <h1 className="text-2xl font-bold text-chocolate mb-6">Назначение рекомендации</h1>

      {/* Форма */}
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="bg-white rounded-2xl shadow p-6 space-y-4 mb-8"
      >
        <div>
          <label className="block text-sm font-medium text-chocolate mb-1">Тип</label>
          <select
            {...register("rec_type")}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-avocado"
          >
            {TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-chocolate mb-1">Название *</label>
          <input
            {...register("name")}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-avocado"
            placeholder="Например: Омега-3"
          />
          {errors.name && (
            <p className="text-tomato text-xs mt-1">{errors.name.message}</p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-chocolate mb-1">Доза</label>
            <input
              {...register("dosage")}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-avocado"
              placeholder="1000 мг"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-chocolate mb-1">Частота</label>
            <input
              {...register("frequency")}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-avocado"
              placeholder="2 раза в день"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-chocolate mb-1">Дата начала</label>
            <input
              type="date"
              {...register("start_date")}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-avocado"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-chocolate mb-1">Дата конца</label>
            <input
              type="date"
              {...register("end_date")}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-avocado"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full bg-tomato text-white py-2.5 rounded-xl font-semibold hover:bg-red-700 disabled:opacity-50"
        >
          {isSubmitting ? "Сохранение..." : "Добавить рекомендацию"}
        </button>
      </form>

      {/* Список существующих */}
      <h2 className="font-semibold text-chocolate mb-3">Все рекомендации</h2>
      {selectedClientRecs.length === 0 ? (
        <p className="text-sm text-gray-400">Нет рекомендаций.</p>
      ) : (
        <div className="space-y-2">
          {selectedClientRecs.map((r) => (
            <div
              key={r.id}
              className={`bg-white rounded-xl shadow px-4 py-3 flex items-center justify-between ${
                !r.is_active ? "opacity-40" : ""
              }`}
            >
              <div>
                <p className="font-medium text-chocolate">{r.name}</p>
                <p className="text-xs text-gray-400">
                  {r.dosage} · {r.frequency}
                </p>
              </div>
              {r.is_active && (
                <button
                  onClick={() => handleDelete(r.id)}
                  className="text-tomato text-sm hover:underline"
                >
                  Деактивировать
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
