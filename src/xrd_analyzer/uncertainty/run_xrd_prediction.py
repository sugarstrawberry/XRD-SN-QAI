"""
XRD预测完整流程脚本
在uncertainty文件夹中运行，自动处理数据并进行预测
"""

import json
import numpy as np
import torch
import os

# 导入本地模块
from dataload import get_simxrd_d_grid
from HybridFeatureDataset import extract_physical_features
from PhyNetCNN import Model
from test import predict_xrd_api

def process_json_to_npy(json_file='test_xrd_data.json', output_file='test_xrd_data.npy'):
    """
    步骤1: 将JSON数据处理成npy格式
    """
    print("步骤1: 处理JSON数据")
    print("-" * 30)
    
    try:
        # 读取JSON数据
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        two_theta = np.array(data['two_theta_values'])
        intensities = np.array(data['intensities'])
        wavelength = data.get('wavelength', 1.5406)
        
        print(f"✓ 读取数据: {len(two_theta)}个点, 2θ范围{two_theta.min():.1f}°-{two_theta.max():.1f}°")
        
        # 使用dataload.py的方法处理
        simxrd_d_grid = get_simxrd_d_grid(wavelength=wavelength)
        
        # 转换到d-spacing
        theta_rad = np.radians(two_theta / 2)
        d_values = wavelength / (2 * np.sin(theta_rad))
        
        # 过滤有效数据
        valid_mask = (np.isfinite(d_values) & 
                      (d_values >= simxrd_d_grid.min()) & 
                      (d_values <= simxrd_d_grid.max()))
        
        d_valid = d_values[valid_mask]
        i_valid = intensities[valid_mask]
        
        if len(d_valid) == 0:
            print("❌ 没有有效数据点!")
            return None
        
        # 插值和归一化
        interpolated = np.interp(simxrd_d_grid, d_valid[::-1], i_valid[::-1])
        if np.max(interpolated) > 0:
            interpolated *= 100 / np.max(interpolated)
        
        # 保存
        np.save(output_file, interpolated)
        print(f"✓ 数据处理完成: {interpolated.shape}, 保存到 {output_file}")
        
        return interpolated
        
    except Exception as e:
        print(f"❌ 数据处理失败: {e}")
        return None

def extract_features_from_npy(npy_file='test_xrd_data.npy'):
    """
    步骤2: 从npy数据提取物理特征
    """
    print("\n步骤2: 提取物理特征")
    print("-" * 30)
    
    try:
        # 加载数据
        intensity_data = np.load(npy_file)
        print(f"✓ 加载数据: {intensity_data.shape}")
        
        # 获取对应的d-spacing网格
        d_grid = get_simxrd_d_grid()
        
        # 提取物理特征
        physical_features = extract_physical_features(d_grid, intensity_data, num_peaks=10)
        print(f"✓ 特征提取完成: {len(physical_features)}维特征")
        
        return intensity_data, physical_features
        
    except Exception as e:
        print(f"❌ 特征提取失败: {e}")
        return None, None

def run_prediction(intensity_data, physical_features, model_path=None):
    """
    步骤3: 执行预测
    """
    print("\n步骤3: 执行预测")
    print("-" * 30)
    
    try:
        # 设置设备
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"✓ 使用设备: {device}")
        
        # 初始化模型
        model = Model().to(device)
        
        # 如果有模型路径，加载权重
        if model_path and os.path.exists(model_path):
            model.load_state_dict(torch.load(model_path, map_location=device))
            print(f"✓ 加载模型权重: {model_path}")
        else:
            print("⚠️  使用随机初始化的模型 (仅用于演示)")
        
        model.eval()
        
        # 执行预测
        results = predict_xrd_api(model, intensity_data, physical_features, device, T=50)
        print("✓ 预测完成")
        
        return results
        
    except Exception as e:
        print(f"❌ 预测失败: {e}")
        return None

def display_and_save_results(results, output_file='prediction_results.json'):
    """
    步骤4: 显示和保存结果
    """
    print("\n步骤4: 预测结果")
    print("=" * 50)
    
    if results is None:
        print("❌ 无预测结果")
        return
    
    # 显示结果
    print(f"全局不确定性 (熵): {results['global_uncertainty']:.4f}")
    print(f"\nTop-5 空间群预测:")
    print("-" * 40)
    print(f"{'排名':<4} {'空间群':<8} {'概率':<12} {'不确定性':<12}")
    print("-" * 40)
    
    for pred in results['top_5_predictions']:
        rank = pred['rank']
        space_group = pred['label'] + 1  # 空间群从1开始
        prob = pred['probability']
        std = pred['std_dev']
        print(f"{rank:<4} {space_group:<8} {prob:<12.4f} {std:<12.4f}")
    
    # 保存结果
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n✓ 结果已保存到: {output_file}")
    except Exception as e:
        print(f"❌ 保存失败: {e}")

def main():
    """
    主函数：完整的XRD预测流程
    """
    print("XRD晶体结构预测系统")
    print("=" * 50)
    print("基于PhyNetCNN模型和Monte Carlo Dropout不确定性估计")
    print("=" * 50)
    
    # 检查输入文件
    if not os.path.exists('test_xrd_data.json'):
        print("❌ 找不到输入文件: test_xrd_data.json")
        return
    
    # 步骤1: 处理JSON数据
    processed_data = process_json_to_npy()
    if processed_data is None:
        return
    
    # 步骤2: 提取特征
    intensity_data, physical_features = extract_features_from_npy()
    if intensity_data is None or physical_features is None:
        return
    
    # 步骤3: 执行预测
    # 如果你有训练好的模型，可以在这里指定路径
    model_path = None  # 例如: 'path/to/your/model.pth'
    results = run_prediction(intensity_data, physical_features, model_path)
    
    # 步骤4: 显示和保存结果
    display_and_save_results(results)
    
    print("\n" + "=" * 50)
    print("预测流程完成!")
    print("=" * 50)
    print("生成的文件:")
    print("  - test_xrd_data.npy (处理后的XRD数据)")
    print("  - prediction_results.json (预测结果)")
    
    if results:
        top_prediction = results['top_5_predictions'][0]
        print(f"\n最可能的空间群: {top_prediction['label'] + 1}")
        print(f"预测概率: {top_prediction['probability']:.2%}")

if __name__ == '__main__':
    main()