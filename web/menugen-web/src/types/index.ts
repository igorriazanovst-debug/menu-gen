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
  targets_meta?: TargetsMeta;
  // MG_504_V_types
  bedtime_hour?: number | null;
  cheat_meal_interval?: number;
  last_cheat_meal_date?: string | null;

}
export interface User {
  id: number; name: string; email?: string; phone?: string;
  vk_id?: string; avatar_url?: string; user_type: string;
  allergies: string[]; disliked_products: string[]; profile?: UserProfile;
  ui_skin?: 'main' | 'second'; // MG_SKIN
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
export type CookingMethod = 'boiled' | 'baked' | 'fried' | 'grilled' | 'raw' | 'stewed' | 'steamed';  // MG_501_V_types
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
  cooking_method?:     CookingMethod | null;  // MG_501_V_types
  has_added_sugar?:    boolean;
  oil_tsp?:            string | number | null;
  serving_size_label?: string | null;
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
  is_cheat_meal?: boolean; // MG_505_V_types
}
export interface Menu {
  creator_name?: string; // MG_B09
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
  currency?: string; // MG_RUBRIC007
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

// MG_205UI_V_types = 1
export type TargetSource = 'auto' | 'user' | 'specialist';

export interface TargetMeta {
  source: TargetSource;
  by_user: { id: number; name: string } | null;
  at: string | null;
}

export type TargetField =
  | 'calorie_target'
  | 'protein_target_g'
  | 'fat_target_g'
  | 'carb_target_g'
  | 'fiber_target_g';

export type TargetsMeta = Partial<Record<TargetField, TargetMeta>>;

export interface TargetAuditEntry {
  id: number;
  field: TargetField;
  source: TargetSource;
  old_value: string | null;
  new_value: string | null;
  reason: string;
  at: string;
  by_user: { id: number; name: string } | null;
}

// ── Fridge ──────────────────────────────────────────────────────────────────
export interface Product {
  id: number;
  name: string;
  category?: string;                // legacy free-form string
  category_id?: number | null;
  category_slug?: string | null;
  category_name?: string | null;
  category_icon?: string | null;
  category_color?: string | null;
  default_unit?: string;
  calories_per_100g?: string | number | null;
  nutrition?: Record<string, number>;
  barcode?: string | null;
  image_url?: string | null;
  is_seed?: boolean;
}
export interface FridgeItem {
  id: number;
  product?: number | null;
  product_name?: string | null;
  product_category?: string | null;          // legacy
  product_category_id?: number | null;
  product_category_slug?: string | null;
  product_category_name?: string | null;
  product_category_icon?: string | null;
  product_category_color?: string | null;
  product_image_url?: string | null;
  name: string;
  quantity?: string | number | null;
  unit?: string;
  expiry_date?: string | null;
  created_at: string;
  updated_at: string;
}
export interface BarcodeLookupResult extends Product {
  source: 'local' | 'openfoodfacts';
}

export interface FridgeMenuUsageRecipe {
  recipe_id: number;
  title: string;
  times: number;
}
export interface FridgeMenuUsage {
  count: number;
  period_days: number;
  recipes: FridgeMenuUsageRecipe[];
}
export interface FridgeItemDetailsResponse {
  item: FridgeItem;
  product: Product | null;
  days_left: number | null;
  usage_30d: FridgeMenuUsage;
}

// ── MG-609 ────────────────────────────────────────────────────────────────
export interface ProductCategory {
  id: number;
  slug: string;
  name_ru: string;
  name_en?: string;
  icon?: string;
  color?: string;
  sort_order?: number;
}

export interface FridgeHistoryItem {
  name: string;
  product_id: number | null;
  category_id: number | null;
  category_slug: string;
  category_name: string;
  category_icon: string;
  category_color: string;
  default_unit: string;
  image_url: string;
  times_used: number;
  last_used: string | null;
}

export interface RecognizedProduct {
  name: string;
  category: string;
  quantity: string | null;
  confidence: number;
  category_id: number | null;
  category_slug: string | null;
  category_name: string | null;
  category_icon: string | null;
  category_color: string | null;
}
export interface RecognizePhotoResponse {
  mode: 'single' | 'multi';
  product?: RecognizedProduct | null;
  products?: RecognizedProduct[];
  raw_text: string;
}

// DIARY_V2 types
export type DiaryNutrition = Partial<Record<'calories' | 'proteins' | 'fats' | 'carbs' | 'sugars' | 'fiber', NutritionValue>>;
export interface DiaryEntry {
  id: number;
  date: string;
  meal_type: MealType;
  recipe?: number | null;
  recipe_title?: string | null;
  custom_name?: string;
  nutrition: DiaryNutrition;
  quantity: number;
  planned_menu_item?: number | null;
  is_eaten: boolean;
  is_planned?: boolean; // DIARY_COPY_V3
  created_at?: string;
}
export interface DiaryNutritionBucket {
  calories: number; proteins: number; fats: number; carbs: number;
}
export interface DiaryDayStats {
  date: string;
  planned: DiaryNutritionBucket;
  actual: DiaryNutritionBucket;
  total: DiaryNutritionBucket;
}
export interface DiaryWaterLog { id?: number; date: string; water_ml: number; }

// MG_SHOP002_web_types — shopping lists v2
export type ShoppingV2Source = 'empty' | 'menu' | 'fridge' | 'ai_text' | 'csv';

// MG_RUBRIC004: rubricator search types.
export interface ShoppingV2RubricResult {
  product_id: number;
  name: string;
  unit: string;
  category_slug: string;
  category_name: string;
  subcategory: string;
}
export interface ShoppingV2RubricSuggestion {
  category_slug: string;
  category_name: string;
}
export interface ShoppingV2RubricResponse {
  query: string;
  results: ShoppingV2RubricResult[];
  suggestion: ShoppingV2RubricSuggestion | null;
}
export interface ShoppingV2Item {
  id: number;
  product_id?: number | null;
  category_slug?: string | null;
  category_name?: string | null;
  name: string;
  quantity?: number | null;
  unit?: string;
  category?: string;
  price_per_unit?: string | null; // MG_RUBRIC008
  line_total?: string | null;
  is_purchased: boolean;
  purchased_by?: number | null;
  purchased_by_name?: string | null;
  purchased_at?: string | null;
  sort_order?: number;
}

export interface ShoppingV2Capabilities {
  read: boolean;
  toggle: boolean;
  export: boolean;
  manage: boolean;
  pending?: boolean; // MG_SHAREACCEPT
}

export interface ShoppingV2ListBrief {
  id: number;
  name: string;
  source: ShoppingV2Source;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  items_total?: number;
  items_purchased?: number;
}

export interface ShoppingV2List extends ShoppingV2ListBrief {
  currency?: string; // MG_RUBRIC008
  total_price?: string | null; // MG_RUBRIC008
  menu?: number | null;
  created_by?: number | null;
  created_by_name?: string | null;
  archived_at?: string | null;
  items: ShoppingV2Item[];
  capabilities?: ShoppingV2Capabilities;
}

export interface ShoppingV2Access {
  id: number;
  user: number;
  user_email: string;
  user_name?: string | null;
  can_read: boolean;
  can_toggle: boolean;
  can_export: boolean;
  status?: 'pending' | 'accepted' | 'rejected'; // MG_SHAREACCEPT
  granted_at: string;
}

// MG_SHAREACCEPT: a list shared TO the current user, awaiting accept/reject.
export interface ShoppingV2PendingList {
  id: number;
  name: string;
  source: ShoppingV2Source;
  items_total?: number;
  items_purchased?: number;
  shared_by_name?: string | null;
  granted_at?: string | null;
}

export interface ShoppingV2ExportCategory {
  category: string;
  items: {
    name: string;
    quantity: string | null;
    unit: string;
    price_per_unit?: string | null; // MG_PRINTWEB001
    line_total?: string | null; // MG_PRINTWEB001
    is_purchased: boolean;
  }[];
}

export interface ShoppingV2ExportData {
  title: string;
  created_at: string;
  currency?: string; // MG_PRINTWEB001
  total_price?: string | null; // MG_PRINTWEB001
  categories: ShoppingV2ExportCategory[];
}

export interface ShoppingV2HistoryEntry {
  id: number;
  name: string;
  quantity?: number | null;
  unit?: string;
  category?: string;
  price_per_unit?: string | null; // MG_HISTWEB001
  purchased_by?: number | null;
  purchased_by_name?: string | null;
  purchased_at: string;
  source_list_id?: number | null;
}


// ─────────────────────────────────────────────────────────────────────────────
// MG_206_V_types: KBJU calculator
// ─────────────────────────────────────────────────────────────────────────────
export type KBJUSystem =
  | 'mifflin'
  | 'harris_benedict'
  | 'rospotrebnadzor'
  | 'efsa'
  | 'custom';

export type KBJUDiet = 'balanced' | 'high_protein' | 'low_carb';

export type KBJUCustomMode = 'grams' | 'percents';

export interface KBJURequest {
  system: KBJUSystem;
  diet?: KBJUDiet | null;
  // base inputs
  height_cm?: number;
  weight_kg?: number | string;
  birth_year?: number;
  gender?: 'male' | 'female' | 'other';
  activity_level?: 'sedentary' | 'light' | 'moderate' | 'active' | 'very_active';
  goal?: 'lose_weight' | 'maintain' | 'gain_weight' | 'healthy';
  // custom
  custom_mode?: KBJUCustomMode | null;
  custom_calorie_target?: number;
  custom_protein_g?: number | string;
  custom_fat_g?: number | string;
  custom_carb_g?: number | string;
  custom_fiber_g?: number | string;
  custom_calorie_delta?: number;
  custom_protein_pct?: number;
  custom_fat_pct?: number;
  custom_carb_pct?: number;
}

export interface KBJUResult {
  system: KBJUSystem;
  diet?: KBJUDiet | null;
  age?: number | null;
  bmr?: number | null;
  tdee?: number | null;
  calorie_target: number;
  protein_target_g: string;
  fat_target_g: string;
  carb_target_g: string;
  fiber_target_g: string;
}
