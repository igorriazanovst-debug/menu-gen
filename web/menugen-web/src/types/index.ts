export type MealPlan = '3' | '5';

export interface NutritionTargets {
  calorie_target: number;
  protein_target_g: string;
  fat_target_g:     string;
  carb_target_g:    string;
  fiber_target_g:   string;
}

export interface UserProfile {
  birth_year?: number; gender?: string; height_cm?: number; weight_kg?: number;
  activity_level: string; goal: string;
  calorie_target?: number;
  protein_target_g?: string | null;
  fat_target_g?:     string | null;
  carb_target_g?:    string | null;
  fiber_target_g?:   string | null;
  meal_plan_type?: MealPlan;
  targets_calculated?: NutritionTargets | null;
}
export interface User {
  id: number; name: string; email?: string; phone?: string;
  vk_id?: string; avatar_url?: string; user_type: string;
  allergies: string[]; disliked_products: string[]; profile?: UserProfile;
  created_at: string;
}
export interface Ingredient { name: string; quantity?: string; unit?: string; }
export interface RecipeStep { text: string; photo?: string; }
export interface NutritionValue { value: string; unit: string; }
export interface Nutrition {
  calories?: NutritionValue; proteins?: NutritionValue;
  fats?: NutritionValue; carbs?: NutritionValue;
  fiber?: NutritionValue; weight?: NutritionValue;
}
export type FoodGroup    = 'grain' | 'protein' | 'vegetable' | 'fruit' | 'dairy' | 'oil' | 'other';
export type ProteinType  = 'animal' | 'plant' | 'mixed';
export type GrainType    = 'whole' | 'refined';
export type SuitableMeal = 'breakfast' | 'lunch' | 'dinner' | 'snack';
export interface Recipe {
  id: number; title: string; cook_time?: string; servings?: number;
  ingredients: Ingredient[]; steps: RecipeStep[]; nutrition: Nutrition;
  categories: string[]; image_url?: string; video_url?: string;
  country?: string; is_custom: boolean; author_name?: string; created_at: string;
  food_group?: FoodGroup | null;
  suitable_for?: SuitableMeal[];
  protein_type?: ProteinType | null;
  grain_type?: GrainType | null;
  is_fatty_fish?: boolean;
  is_red_meat?: boolean;
}
export type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack';
export const MEAL_LABELS: Record<MealType, string> = {
  breakfast: 'Завтрак', lunch: 'Обед', dinner: 'Ужин', snack: 'Перекус',
};
export type ComponentRole =
  | 'protein' | 'grain' | 'vegetable' | 'fruit' | 'dairy' | 'oil' | 'other';

export type MealSlot =
  | 'breakfast' | 'lunch' | 'dinner' | 'snack1' | 'snack2';

export const COMPONENT_ROLE_LABELS: Record<ComponentRole, string> = {
  protein:   'Белок',
  grain:     'Крупа/гарнир',
  vegetable: 'Овощи',
  fruit:     'Фрукт',
  dairy:     'Молочное',
  oil:       'Масло',
  other:     'Прочее',
};

export const COMPONENT_ROLE_ICONS: Record<ComponentRole, string> = {
  protein:   '🍗',
  grain:     '🌾',
  vegetable: '🥗',
  fruit:     '🍎',
  dairy:     '🥛',
  oil:       '🫒',
  other:     '🍽',
};

export interface MenuItem {
  id: number; day_offset: number; meal_type: MealType;
  meal_slot?: MealSlot | string;
  component_role?: ComponentRole;
  recipe: Recipe; member_name?: string; quantity: number;
}
export interface Menu {
  id: number; start_date: string; end_date: string; period_days: number;
  status: string; filters_used: Record<string, unknown>;
  generated_at: string; updated_at: string; items: MenuItem[];
}
export interface ShoppingItem {
  id: number; name: string; quantity?: number; unit?: string;
  category?: string; is_purchased: boolean;
}
export interface ShoppingList { id: number; items: ShoppingItem[]; created_at: string; }
// MG_204_V_types = 1
export interface FamilyMember {
  id: number; user_id: number; name: string; email?: string;
  avatar_url?: string; role: 'head' | 'member' | 'owner'; joined_at: string;
  allergies?: string[];
  disliked_products?: string[];
  profile?: UserProfile | null;
}
export interface Family {
  id: number; name: string; owner_name: string;
  members: FamilyMember[]; created_at: string;
}
export interface SubscriptionPlan {
  id: number; code: string; name: string; price: string;
  period: 'month' | 'year'; features: Record<string, unknown>;
  max_family_members: number;
}
export interface Subscription {
  id: number; plan: SubscriptionPlan; status: string;
  started_at: string; expires_at: string; auto_renew: boolean;
}
export interface PaginatedResponse<T> {
  count: number; next?: string; previous?: string; results: T[];
}
export interface AuthTokens { access: string; refresh: string; }
